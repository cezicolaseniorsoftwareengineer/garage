"""Authentication API routes -- register and login."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.user import User


router = APIRouter(prefix="/api/auth", tags=["auth"])

_user_repo = None


def init_auth_routes(user_repo):
    global _user_repo
    _user_repo = user_repo


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=100)
    username: str = Field(..., min_length=3, max_length=30)
    email: str = Field(..., min_length=5, max_length=120)
    whatsapp: str = Field(..., min_length=10, max_length=20)
    profession: str = Field(..., pattern="^(autonomo|estudante|empresario)$")
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/register")
def api_register(req: RegisterRequest):
    """Register a new user account."""
    if _user_repo.exists_username(req.username):
        raise HTTPException(status_code=409, detail="Nome de usuario ja existe.")

    if _user_repo.exists_email(req.email):
        raise HTTPException(status_code=409, detail="Email ja cadastrado.")

    salt = User.generate_salt()
    password_hash = User.hash_password(req.password, salt)

    user = User(
        full_name=req.full_name,
        username=req.username,
        email=req.email,
        whatsapp=req.whatsapp,
        profession=req.profession,
        password_hash=password_hash,
        salt=salt,
    )

    _user_repo.save(user)

    return {
        "success": True,
        "message": "Cadastro realizado com sucesso.",
        "user": user.to_public_dict(),
    }


@router.post("/login")
def api_login(req: LoginRequest):
    """Authenticate user with username and password."""
    user = _user_repo.find_by_username(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario ou senha incorretos.")

    if not user.verify_password(req.password):
        raise HTTPException(status_code=401, detail="Usuario ou senha incorretos.")

    return {
        "success": True,
        "message": "Login realizado com sucesso.",
        "user": user.to_public_dict(),
    }
