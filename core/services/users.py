from db.models import User, Scan
from core.services.exceptions import NotFound
from core.crypto import encrypt_password


def get_user_by_email(db, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if not user:
        raise NotFound(f"User {email} not found")
    return user


def update_profile(db, user_id: int, data: dict, encryption_key: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFound(f"User {user_id} not found")
    allowed = {"email", "telegram_chat_id", "recreationgov_email", "recreationgov_password"}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key == "recreationgov_password":
            user.recreationgov_password = encrypt_password(value, encryption_key)
        else:
            setattr(user, key, value)
    db.flush()
    return user


def scans_used(db, user_id: int) -> int:
    return (
        db.query(Scan)
        .filter(Scan.user_id == user_id, Scan.deleted_at.is_(None))
        .count()
    )
