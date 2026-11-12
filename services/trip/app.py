from datetime import date
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Integer, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, Session
from database import Base, engine, get_db
from security import current_user

app=FastAPI(title="TripPack Trip Service",version="1.0.0")
Instrumentator().instrument(app).expose(app)
class Trip(Base):
    __tablename__="trips"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_id:Mapped[int]=mapped_column(Integer,index=True)
    title:Mapped[str]=mapped_column(String(150))
    trip_type:Mapped[str]=mapped_column(String(30))
    start_date:Mapped[date]=mapped_column(Date)
    end_date:Mapped[date]=mapped_column(Date)
    description:Mapped[str]=mapped_column(Text,default="")
Base.metadata.create_all(bind=engine)
class TripIn(BaseModel):
    title:str=Field(min_length=1,max_length=150)
    trip_type:str
    start_date:date
    end_date:date
    description:str=""
class TripUpdate(BaseModel):
    title:str|None=None
    trip_type:str|None=None
    start_date:date|None=None
    end_date:date|None=None
    description:str|None=None
def out(t): return {"id":t.id,"owner_id":t.owner_id,"title":t.title,"trip_type":t.trip_type,"start_date":t.start_date,"end_date":t.end_date,"description":t.description}
@app.get("/health")
def health(): return {"status":"ok","service":"trip-service"}
@app.post("/trips",status_code=201)
def create_trip(data:TripIn,user=Depends(current_user),db:Session=Depends(get_db)):
    if data.end_date<data.start_date: raise HTTPException(400,"end_date must not be before start_date")
    t=Trip(owner_id=user["id"],**data.model_dump()); db.add(t); db.commit(); db.refresh(t); return out(t)
@app.get("/trips")
def list_trips(user=Depends(current_user),db:Session=Depends(get_db)):
    q=db.query(Trip)
    if user["role"]!="admin": q=q.filter(Trip.owner_id==user["id"])
    return [out(t) for t in q.order_by(Trip.id.desc()).all()]
@app.get("/trips/{trip_id}")
def get_trip(trip_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
    t=db.get(Trip,trip_id)
    if not t or (t.owner_id!=user["id"] and user["role"]!="admin"): raise HTTPException(404,"Trip not found")
    return out(t)
@app.put("/trips/{trip_id}")
def update_trip(trip_id:int,data:TripUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    t=db.get(Trip,trip_id)
    if not t or (t.owner_id!=user["id"] and user["role"]!="admin"): raise HTTPException(404,"Trip not found")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(t,k,v)
    if t.end_date<t.start_date: raise HTTPException(400,"end_date must not be before start_date")
    db.commit(); db.refresh(t); return out(t)
@app.delete("/trips/{trip_id}")
def delete_trip(trip_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
    t=db.get(Trip,trip_id)
    if not t or (t.owner_id!=user["id"] and user["role"]!="admin"): raise HTTPException(404,"Trip not found")
    db.delete(t); db.commit(); return {"deleted":trip_id}
