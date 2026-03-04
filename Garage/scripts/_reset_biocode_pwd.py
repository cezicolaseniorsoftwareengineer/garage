#!/usr/bin/env python3
"""Reset biocode password directly in production database."""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.database import get_db
from app.infrastructure.repositories.user_repository import UserRepository
from passlib.context import CryptContext
import secrets
import string

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_password(length=12):
    """Generate secure random password."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def main():
    # Generate new password
    new_password = generate_password()

    # Hash password
    hashed = pwd_context.hash(new_password)

    # Update in database
    db = next(get_db())
    user_repo = UserRepository(db)

    # Find biocode user
    biocode = user_repo.get_by_email("biocodetechnology@gmail.com")
    if not biocode:
        print("❌ Usuário biocode não encontrado!")
        return

    # Update password
    user_repo.update_password(biocode.id, hashed)

    print()
    print("═" * 60)
    print("SENHA DO BIOCODE RESETADA COM SUCESSO")
    print("═" * 60)
    print()
    print(f"URL:      https://garage-0lw9.onrender.com/")
    print(f"Username: {biocode.username}")
    print(f"Senha:    {new_password}")
    print()
    print("═" * 60)
    print()
    print("APÓS O LOGIN:")
    print("  • Jogo:  https://garage-0lw9.onrender.com/jogo")
    print("  • Conta: https://garage-0lw9.onrender.com/account")
    print()

if __name__ == "__main__":
    main()
