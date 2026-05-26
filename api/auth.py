import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
EXPIRE_HOURS = 24
COOKIE_NAME = "campbuddy_session"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, secret_key: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "exp": exp, "iat": now},
        secret_key,
        algorithm=ALGORITHM,
    )


def decode_token(token: str, secret_key: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except JWTError as e:
        logger.warning("Invalid JWT token: %s", e)
        return None
    except (ValueError, KeyError) as e:
        logger.warning("Malformed JWT payload: %s", e)
        return None
