import logging
import os
from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.id_generator import generate_user_id, generate_admin_id
from schemas.dto import (
    UserLogin,
    Token,
    AdminCreate,
    DeveloperOverrideRequest,
    PasswordChangeRequest,
    AdminPasswordResetRequest,
)
from core.security import get_password_hash, verify_password, create_access_token
from core.db_errors import db_integrity_http_exception
from core.database import SessionLocal
from models.sql_models import User, Role, UserRole, Admin
from services.notification_client import send_email_notification

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

ENABLE_DEVELOPER_OVERRIDE = os.getenv("ENABLE_DEVELOPER_OVERRIDE", "false").strip().lower() in {"1", "true", "yes"}
DEVELOPER_OVERRIDE_TOKEN = os.getenv("DEVELOPER_OVERRIDE_TOKEN", "")
DEVELOPER_ALLOWED_IPS = {
    ip.strip() for ip in os.getenv("DEVELOPER_ALLOWED_IPS", "127.0.0.1,::1").split(",") if ip.strip()
}


def _decode_bearer_claims(request: Request) -> dict | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None

    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        return None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/create-admin", status_code=status.HTTP_201_CREATED, response_model=Token)
@limiter.limit("5/minute")
def create_admin(request: Request, admin_data: AdminCreate, db: Session = Depends(get_db)):
    normalized_email = admin_data.email.lower().strip()

    try:
        existing_admin_count = db.query(Admin.id).count()
        if existing_admin_count > 0:
            claims = _decode_bearer_claims(request)
            if not claims:
                raise HTTPException(
                    status_code=401,
                    detail="Authorization token is required after bootstrap admin creation",
                )

            caller_role = (claims.get("role") or "").upper()
            if caller_role not in {"ADMIN", "SUPERADMIN"}:
                raise HTTPException(
                    status_code=403,
                    detail="Only ADMIN or SUPERADMIN can create additional admin users",
                )

        existing_user = db.query(User).filter(User.email == normalized_email).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email already registered")

        hashed_password = get_password_hash(admin_data.password)

        user_id = generate_user_id(db)
        admin_id = generate_admin_id(db)

        new_user = User(
            id=user_id,
            email=normalized_email,
            hashed_password=hashed_password,
            is_active=True
        )
        db.add(new_user)
        db.flush()

        admin_role = db.query(Role).filter(Role.role_name == "ADMIN").first()
        if not admin_role:
            raise HTTPException(status_code=500, detail="ADMIN role not found")

        db.add(UserRole(user_id=user_id, role_id=admin_role.id))

        db.add(Admin(
            id=admin_id,
            user_id=user_id,
            name=admin_data.name,
            phone=admin_data.phone,
            designation=admin_data.designation,
            address=admin_data.address
        ))

        db.commit()

        send_email_notification(
            recipient_email=normalized_email,
            subject="Your School ERP admin account is ready",
            body="Your admin account has been created successfully. Please sign in using your registered email.",
            event_type="ADMIN_ACCOUNT_CREATED",
        )

        token = create_access_token(data={"sub": user_id, "role": "ADMIN"})
        return {"access_token": token, "token_type": "bearer", "role": "ADMIN"}

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        raise db_integrity_http_exception(exc, fallback_status=409, fallback_detail="Failed to create admin")

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email.lower().strip()).first()

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    user_roles = (
        db.query(Role.role_name)
        .join(UserRole, Role.id == UserRole.role_id)
        .filter(UserRole.user_id == user.id)
        .all()
    )

    if not user_roles:
        raise HTTPException(status_code=403, detail="Role not assigned")

    role_priority = {
        "SUPERADMIN": 100,
        "ADMIN": 80,
        "TEACHER": 70,
        "STUDENT": 60,
        "PARENT": 50,
        "NON_TEACHING_STAFF": 40,
        "SERVICE": 30,
    }
    role_name = sorted(
        [row[0] for row in user_roles],
        key=lambda role: (-role_priority.get(role, 0), role),
    )[0]
    token = create_access_token(data={"sub": user.id, "role": role_name})

    return {"access_token": token, "token_type": "bearer", "role": role_name}


@router.post("/_internal/dev-token", response_model=Token, include_in_schema=False)
@limiter.limit("3/minute")
def create_developer_override_token(
    request: Request,
    payload: DeveloperOverrideRequest,
):
    """Hidden developer-only token minting endpoint guarded by env controls."""
    if not ENABLE_DEVELOPER_OVERRIDE:
        raise HTTPException(status_code=404, detail="Not found")

    if not DEVELOPER_OVERRIDE_TOKEN:
        raise HTTPException(status_code=503, detail="Developer override is not configured")

    caller_ip = request.client.host if request.client else "unknown"
    if DEVELOPER_ALLOWED_IPS and caller_ip not in DEVELOPER_ALLOWED_IPS:
        logger.warning(
            "dev_override_denied_ip",
            extra={"event": "dev_override_denied_ip", "ip": caller_ip},
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    supplied_token = request.headers.get("X-Developer-Token", "")
    if not compare_digest(supplied_token, DEVELOPER_OVERRIDE_TOKEN):
        logger.warning(
            "dev_override_denied_token",
            extra={"event": "dev_override_denied_token", "ip": caller_ip},
        )
        raise HTTPException(status_code=401, detail="Invalid developer credentials")

    if payload.role.value not in {"SUPERADMIN"}:
        raise HTTPException(status_code=400, detail="Only developer roles are allowed")

    token = create_access_token(data={"sub": payload.subject, "role": payload.role.value})
    logger.warning(
        "dev_override_token_issued",
        extra={
            "event": "dev_override_token_issued",
            "ip": caller_ip,
            "subject": payload.subject,
            "role": payload.role.value,
        },
    )

    return {"access_token": token, "token_type": "bearer", "role": payload.role.value}


# =====================================================================
# HELPERS — re-useable JWT → user resolver for admin endpoints
# =====================================================================
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_SECRET_KEY = os.getenv("SECRET_KEY", "")
_ALGORITHM = "HS256"


def _get_current_admin(token: str = Depends(_oauth2_scheme)):
    """Require either ADMIN or SUPERADMIN to call user-management endpoints."""
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        if role not in {"ADMIN", "SUPERADMIN"}:
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return {"user_id": user_id, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


def _get_current_user(token: str = Depends(_oauth2_scheme)):
    """Resolve authenticated user from JWT for self-service account actions."""
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": user_id, "role": payload.get("role", "")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


# =====================================================================
# USER MANAGEMENT  (admin / superadmin only)
# =====================================================================

@router.patch("/change-password", status_code=200)
def change_own_password(
    request: Request,
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(_get_current_user),
):
    """Allow authenticated users to change their own password."""
    user = db.get(User, current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    user.hashed_password = get_password_hash(payload.new_password)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise db_integrity_http_exception(exc, fallback_status=400, fallback_detail="Could not update password")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

    return {"message": "Password updated successfully"}


@router.get("/admin/users")
def list_users(
    role: str = Query(None, description="Filter by role name"),
    is_active: bool = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin=Depends(_get_current_admin),
):
    """List all users with their roles. Filterable by role and active status."""
    query = (
        db.query(
            User.id,
            User.email,
            User.is_active,
            User.created_at,
            Role.role_name,
        )
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
    )

    if role:
        query = query.filter(Role.role_name == role.upper())
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "users": [
            {
                "id": r.id,
                "email": r.email,
                "is_active": r.is_active,
                "role": r.role_name,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.patch("/admin/users/{user_id}/deactivate", status_code=200)
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin=Depends(_get_current_admin),
):
    """Set a user account to inactive (soft-disable). Admins cannot deactivate SUPERADMIN accounts."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deactivation
    if user.id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    # Prevent ADMIN from touching SUPERADMIN accounts
    user_role = (
        db.query(Role.role_name)
        .join(UserRole, Role.id == UserRole.role_id)
        .filter(UserRole.user_id == user_id)
        .first()
    )
    if user_role and user_role[0] in {"SUPERADMIN"} and admin["role"] == "ADMIN":
        raise HTTPException(status_code=403, detail="Insufficient privileges to deactivate this account")

    if not user.is_active:
        return {"message": "User is already inactive", "user_id": user_id}

    user.is_active = False
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise db_integrity_http_exception(exc, fallback_status=409, fallback_detail="Could not deactivate user")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

    return {"message": "User deactivated successfully", "user_id": user_id}


@router.patch("/admin/users/{user_id}/activate", status_code=200)
def activate_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin=Depends(_get_current_admin),
):
    """Reactivate a previously deactivated user account."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent ADMIN from touching SUPERADMIN accounts
    user_role = (
        db.query(Role.role_name)
        .join(UserRole, Role.id == UserRole.role_id)
        .filter(UserRole.user_id == user_id)
        .first()
    )
    if user_role and user_role[0] in {"SUPERADMIN"} and admin["role"] == "ADMIN":
        raise HTTPException(status_code=403, detail="Insufficient privileges to activate this account")

    if user.is_active:
        return {"message": "User is already active", "user_id": user_id}

    user.is_active = True
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise db_integrity_http_exception(exc, fallback_status=409, fallback_detail="Could not activate user")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

    return {"message": "User activated successfully", "user_id": user_id}


@router.get("/admin/users/{user_id}")
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(_get_current_admin),
):
    """Get a single user with their role."""
    row = (
        db.query(
            User.id,
            User.email,
            User.is_active,
            User.created_at,
            Role.role_name,
        )
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(User.id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": row.id,
        "email": row.email,
        "is_active": row.is_active,
        "role": row.role_name,
        "created_at": row.created_at,
    }


@router.patch("/admin/users/{user_id}/password", status_code=200)
def admin_reset_user_password(
    request: Request,
    user_id: str,
    payload: AdminPasswordResetRequest,
    db: Session = Depends(get_db),
    admin=Depends(_get_current_admin),
):
    """Allow ADMIN/SUPERADMIN to set a new password for any user account."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_roles = {
        row[0]
        for row in db.query(Role.role_name)
        .join(UserRole, Role.id == UserRole.role_id)
        .filter(UserRole.user_id == user_id)
        .all()
    }

    if "SUPERADMIN" in user_roles and admin["role"] == "ADMIN":
        raise HTTPException(status_code=403, detail="Insufficient privileges to change this user's password")

    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    user.hashed_password = get_password_hash(payload.new_password)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise db_integrity_http_exception(exc, fallback_status=400, fallback_detail="Could not update password")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

    return {"message": "Password updated successfully", "user_id": user_id}
