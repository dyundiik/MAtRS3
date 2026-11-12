import os
from datetime import datetime
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, Session
from passlib.context import CryptContext
from database import Base, engine, get_db
from security import create_token, current_user, admin_required

app = FastAPI(title="TripPack Auth Service", version="1.0.0")
Instrumentator().instrument(app).expose(app)
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    email: Mapped[str]=mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    full_name: Mapped[str]=mapped_column(String(120), default="")
    role: Mapped[str]=mapped_column(String(20), default="user")
    created_at: Mapped[datetime]=mapped_column(DateTime, server_default=func.now())

Base.metadata.create_all(bind=engine)
# Optional administrator bootstrap. Configure ADMIN_EMAIL and ADMIN_PASSWORD in .env.
with next(get_db()) as _db:
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_email and admin_password and not _db.query(User).filter_by(email=admin_email.lower()).first():
        _db.add(User(email=admin_email.lower(), password_hash=pwd.hash(admin_password),
                     full_name="TripPack Administrator", role="admin"))
        _db.commit()

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
class LoginIn(BaseModel):
    email: EmailStr
    password: str
class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)

@app.get("/health")
def health(): return {"status":"ok","service":"auth-service"}
@app.post("/auth/register", status_code=201)
def register(data:RegisterIn, db:Session=Depends(get_db)):
    email=data.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409,"Email already registered")
    user=User(email=email,password_hash=pwd.hash(data.password),full_name=data.full_name.strip(),role="user")
    db.add(user); db.commit(); db.refresh(user)
    return {"id":user.id,"email":user.email,"full_name":user.full_name,"role":user.role}
@app.post("/auth/login")
def login(data:LoginIn, db:Session=Depends(get_db)):
    user=db.query(User).filter_by(email=data.email.lower()).first()
    if not user or not pwd.verify(data.password,user.password_hash):
        raise HTTPException(401,"Incorrect email or password")
    token=create_token(user.id,user.role)
    return {"access_token":token,"token_type":"bearer","expires_in":28800,
            "user":{"id":user.id,"email":user.email,"full_name":user.full_name,"role":user.role}}
@app.post("/auth/logout")
def logout(user=Depends(current_user)):
    # JWT is stateless: the client must discard the token after logout.
    return {"message":"Logged out. Discard the access token on the client."}
@app.get("/users/me")
def my_profile(user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.get(User,user["id"])
    if not row: raise HTTPException(404,"User not found")
    return {"id":row.id,"email":row.email,"full_name":row.full_name,"role":row.role,"created_at":row.created_at}
@app.put("/users/me")
def update_profile(data:ProfileUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.get(User,user["id"])
    if not row: raise HTTPException(404,"User not found")
    row.full_name=data.full_name.strip(); db.commit(); db.refresh(row)
    return {"id":row.id,"email":row.email,"full_name":row.full_name,"role":row.role}
@app.get("/users")
def list_users(user=Depends(current_user),db:Session=Depends(get_db)):
    admin_required(user)
    return [{"id":u.id,"email":u.email,"full_name":u.full_name,"role":u.role} for u in db.query(User).all()]
@app.patch("/users/{user_id}/role")
def set_role(user_id:int, role:str, user=Depends(current_user),db:Session=Depends(get_db)):
    admin_required(user)
    if role not in ("user","admin"): raise HTTPException(400,"Role must be user or admin")
    row=db.get(User,user_id)
    if not row: raise HTTPException(404,"User not found")
    row.role=role; db.commit()
    return {"id":row.id,"role":row.role}
