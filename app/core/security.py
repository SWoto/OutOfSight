import bcrypt

def get_hashed_password(password: str) -> bytes:
    pwd_bytes = password.encode('utf-8')
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=bcrypt.gensalt())
    return hashed_password

def check_password(provided_password: str, hashed_password: bytes) -> bool:
    password_byte_enc = provided_password.encode('utf-8')
    return bcrypt.checkpw(password=password_byte_enc, hashed_password=hashed_password)