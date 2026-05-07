import pytest
from cryptography.fernet import Fernet
from core.crypto import encrypt_password, decrypt_password


def test_roundtrip():
    key = Fernet.generate_key().decode()
    assert decrypt_password(encrypt_password("s3cr3t!", key), key) == "s3cr3t!"


def test_ciphertext_differs_each_call():
    key = Fernet.generate_key().decode()
    assert encrypt_password("same", key) != encrypt_password("same", key)


def test_wrong_key_raises():
    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    with pytest.raises(Exception):
        decrypt_password(encrypt_password("secret", key1), key2)


def test_encrypted_is_string():
    key = Fernet.generate_key().decode()
    result = encrypt_password("password", key)
    assert isinstance(result, str)
