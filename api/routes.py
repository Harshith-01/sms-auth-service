from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.id_generator import generate_user_id, generate_admin_id
from schemas.dto import UserLogin, Token, AdminCreate
from core.security import get_password_hash, verify_password, create_access_token
from core.database import SessionLocal
from models.sql_models import User, Role, UserRole, Admin

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/create-admin", status_code=status.HTTP_201_CREATED, response_model=Token)
@limiter.limit("5/minute")
def create_admin(request: Request, admin_data: AdminCreate, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(User).filter(User.email == admin_data.email).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email already registered")

        hashed_password = get_password_hash(admin_data.password)

        user_id = generate_user_id(db)
        admin_id = generate_admin_id(db)

        new_user = User(
            id=user_id,
            email=admin_data.email,
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

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

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
