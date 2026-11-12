import os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Header, HTTPException

SECRET_KEY = os.getenv("JWT_SECRET", "CHANGE_THIS_DEVELOPMENT_SECRET")
ALGORITHM = "HS256"

def create_token(user_id: int, role: str):
    payload = {
        "sub": str(user_id), "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token is required")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": int(payload["sub"]), "role": payload.get("role", "user")}
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def admin_required(user):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
