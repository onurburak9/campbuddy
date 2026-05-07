from cryptography.fernet import Fernet


def encrypt_password(plaintext: str, key: str) -> str:
    return Fernet(key.encode("ascii")).encrypt(plaintext.encode()).decode("ascii")


def decrypt_password(encrypted: str, key: str) -> str:
    return Fernet(key.encode("ascii")).decrypt(encrypted.encode("ascii")).decode()
