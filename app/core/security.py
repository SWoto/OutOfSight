import bcrypt
from pydantic import SecretStr


def get_hashed_password(password: SecretStr) -> bytes:
    pwd = password.get_secret_value()
    pwd_bytes = pwd.encode('utf-8')
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=bcrypt.gensalt())
    return hashed_password


def check_password(provided_password: str, hashed_password: bytes) -> bool:
    pwd = provided_password
    password_byte_enc = str(pwd).encode('utf-8')
    return bcrypt.checkpw(password=password_byte_enc, hashed_password=hashed_password)
