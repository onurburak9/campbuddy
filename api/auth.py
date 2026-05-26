from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import jwt, JWTError

ALGORITHM = "HS256"
EXPIRE_HOURS = 24
COOKIE_NAME = "campbuddy_session"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: int, secret_key: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, secret_key, algorithm=ALGORITHM)


def decode_token(token: str, secret_key: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        return None
