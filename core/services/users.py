import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from db.models import User, Scan, PasswordResetToken
from core.services.exceptions import NotFound, InvalidState
from core.crypto import encrypt_password


def get_user_by_email(db, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if not user:
        raise NotFound("User not found")
    return user


def update_profile(db, user_id: int, data: dict, encryption_key: str) -> User:
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise NotFound(f"User {user_id} not found")
    allowed = {"email", "telegram_chat_id", "recreationgov_email", "recreationgov_password"}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key == "recreationgov_password":
            user.recreationgov_password = encrypt_password(value, encryption_key) if value else None
        else:
            setattr(user, key, value)
    if not (user.recreationgov_email and user.recreationgov_password):
        db.query(Scan).filter(
            Scan.user_id == user.id, Scan.deleted_at.is_(None)
        ).update({"auto_book": False}, synchronize_session="fetch")
    db.flush()
    return user


def scans_used(db, user_id: int) -> int:
    return (
        db.query(Scan)
        .filter(Scan.user_id == user_id, Scan.deleted_at.is_(None))
        .count()
    )


def register_user(db, email: str, hashed_password: str) -> User:
    existing = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if existing:
        raise InvalidState("Email already in use")
    user = User(email=email, hashed_password=hashed_password)
    db.add(user)
    db.flush()
    return user


def create_password_reset_token(db, email: str) -> Optional[str]:
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if not user:
        return None
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
    ).update({"used_at": datetime.now(timezone.utc)}, synchronize_session="fetch")
    raw_token = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(token)
    db.flush()
    return raw_token


def reset_password_with_token(db, raw_token: str, hashed_password: str) -> User:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.now(timezone.utc),
    ).first()
    if not token:
        raise NotFound("Invalid or expired reset link")
    user = db.query(User).filter(User.id == token.user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise NotFound("Invalid or expired reset link")
    token.used_at = datetime.now(timezone.utc)
    user.hashed_password = hashed_password
    db.flush()
    return user
