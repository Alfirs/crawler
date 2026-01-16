import os, time, jwt
SECRET = os.getenv("JWT_SECRET", "change_me")
TTL_MIN = int(os.getenv("JWT_TTL_MIN", "1440"))

def make_signed_token(payload: dict) -> str:
    data = dict(payload)
    data["exp"] = int(time.time()) + TTL_MIN * 60
    data["iat"] = int(time.time())
    return jwt.encode(data, SECRET, algorithm="HS256")

def verify_token(token: str):
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except Exception:
        return None
