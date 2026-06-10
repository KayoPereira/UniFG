from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

from ..database import create_admin_user, get_admin_user_by_email


class AuthService:
    def register(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        if not email or not password:
            raise ValueError("Email e senha são obrigatórios.")
        if len(password) < 8:
            raise ValueError("A senha deve ter pelo menos 8 caracteres.")
        if get_admin_user_by_email(email):
            raise ValueError("Este email já está cadastrado.")
        return create_admin_user(email, generate_password_hash(password))

    def authenticate(self, email: str, password: str) -> dict | None:
        email = email.strip().lower()
        user = get_admin_user_by_email(email)
        if not user:
            return None
        if not check_password_hash(user["password_hash"], password):
            return None
        return user
