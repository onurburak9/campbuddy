from cryptography.fernet import Fernet


def encrypt_password(plaintext: str, key: str) -> str:
    return Fernet(key.encode()).encrypt(plaintext.encode()).decode()


def decrypt_password(encrypted: str, key: str) -> str:
    return Fernet(key.encode()).decrypt(encrypted.encode()).decode()
