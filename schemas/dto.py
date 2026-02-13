from pydantic import BaseModel, EmailStr, Field, ConfigDict
from enum import Enum
from typing import Optional

class RoleEnum(str, Enum):
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"

class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

class AdminCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=15)
    designation: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = Field(default=None, max_length=255)

class AdminOut(BaseModel):
    id: str
    name: str
    phone: Optional[str]
    designation: Optional[str]
    address: Optional[str]

    model_config = ConfigDict(from_attributes=True)
