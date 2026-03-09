import logging
import os
from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.id_generator import generate_user_id, generate_admin_id
from schemas.dto import UserLogin, Token, AdminCreate, DeveloperOverrideRequest
from core.security import get_password_hash, verify_password, create_access_token
from core.database import SessionLocal
from models.sql_models import User, Role, UserRole, Admin

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

ENABLE_DEVELOPER_OVERRIDE = os.getenv("ENABLE_DEVELOPER_OVERRIDE", "false").strip().lower() in {"1", "true", "yes"}
DEVELOPER_OVERRIDE_TOKEN = os.getenv("DEVELOPER_OVERRIDE_TOKEN", "")
DEVELOPER_ALLOWED_IPS = {
    ip.strip() for ip in os.getenv("DEVELOPER_ALLOWED_IPS", "127.0.0.1,::1").split(",") if ip.strip()
}

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

        token = create_access_token(data={"sub": user_id, "role": "ADMIN"})
        return {"access_token": token, "token_type": "bearer", "role": "ADMIN"}

    except HTTPException:
        db.rollback()
        raise

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

    user_role = (
        db.query(Role.role_name)
        .join(UserRole, Role.id == UserRole.role_id)
        .filter(UserRole.user_id == user.id)
        .first()
    )

    if not user_role:
        raise HTTPException(status_code=403, detail="Role not assigned")

    role_name = user_role[0]
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

    if payload.role.value not in {"SUPERADMIN", "SUPERADMIN1"}:
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
