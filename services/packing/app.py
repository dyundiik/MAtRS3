import os, json
import httpx
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, Session, relationship
from database import Base, engine, get_db
from security import current_user

CATEGORY_URL=os.getenv("CATEGORY_SERVICE_URL","http://categorization-service:8000")
TRIP_URL=os.getenv("TRIP_SERVICE_URL","http://trip-service:8000")
app=FastAPI(title="TripPack Packing Service",version="1.0.0")
Instrumentator().instrument(app).expose(app)
class PackingList(Base):
    __tablename__="packing_lists"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    trip_id:Mapped[int]=mapped_column(Integer,index=True)
    owner_id:Mapped[int]=mapped_column(Integer,index=True)
    title:Mapped[str]=mapped_column(String(150))
    shared_with:Mapped[str]=mapped_column(Text,default="[]")
    items:Mapped[list["Item"]]=relationship(back_populates="packing_list",cascade="all, delete-orphan")
class Item(Base):
    __tablename__="items"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    list_id:Mapped[int]=mapped_column(ForeignKey("packing_lists.id",ondelete="CASCADE"),index=True)
    name:Mapped[str]=mapped_column(String(150))
    category:Mapped[str]=mapped_column(String(50),default="інше")
    quantity:Mapped[int]=mapped_column(Integer,default=1)
    is_packed:Mapped[bool]=mapped_column(Boolean,default=False)
    note:Mapped[str]=mapped_column(Text,default="")
    packing_list:Mapped[PackingList]=relationship(back_populates="items")
Base.metadata.create_all(bind=engine)
class ListIn(BaseModel):
    trip_id:int
    title:str=Field(min_length=1,max_length=150)
    trip_type:str="відпочинок"
class ListUpdate(BaseModel): title:str=Field(min_length=1,max_length=150)
class ItemIn(BaseModel):
    name:str=Field(min_length=1,max_length=150)
    category:str="інше"
    quantity:int=Field(default=1,ge=1,le=1000)
    note:str=""
class ItemUpdate(BaseModel):
    name:str|None=None
    category:str|None=None
    quantity:int|None=Field(default=None,ge=1,le=1000)
    is_packed:bool|None=None
    note:str|None=None
class ShareIn(BaseModel): user_id:int
def can_access(l,u):
    shared=set(json.loads(l.shared_with or "[]"))
    return l.owner_id==u["id"] or u["id"] in shared or u["role"]=="admin"
def list_out(l):
    return {"id":l.id,"trip_id":l.trip_id,"owner_id":l.owner_id,"title":l.title,
            "shared_with":json.loads(l.shared_with or "[]"),
            "items":[item_out(i) for i in l.items]}
def item_out(i):
    return {"id":i.id,"list_id":i.list_id,"name":i.name,"category":i.category,"quantity":i.quantity,"is_packed":i.is_packed,"note":i.note}
@app.get("/health")
def health(): return {"status":"ok","service":"packing-service"}
@app.post("/lists",status_code=201)
def create_list(data:ListIn,authorization:str|None=Header(default=None),user=Depends(current_user),db:Session=Depends(get_db)):
    # Verify that the trip exists and belongs to the authenticated user (or caller is admin).
    try:
        check=httpx.get(f"{TRIP_URL}/trips/{data.trip_id}",headers={"Authorization":authorization or ""},timeout=4)
        if check.status_code != 200:
            raise HTTPException(404,"Trip not found or access denied")
    except httpx.HTTPError:
        raise HTTPException(503,"Trip Service is unavailable")
    l=PackingList(trip_id=data.trip_id,owner_id=user["id"],title=data.title)
    db.add(l); db.commit(); db.refresh(l)
    # Generate starter items from trip type through categorization service.
    try:
        response=httpx.get(f"{CATEGORY_URL}/suggestions/{data.trip_type}",timeout=4)
        if response.status_code==200:
            for x in response.json():
                db.add(Item(list_id=l.id,name=x["name"],category=x["category"],quantity=x.get("quantity",1)))
            db.commit(); db.refresh(l)
    except httpx.HTTPError:
        pass
    return list_out(l)
@app.get("/lists")
def get_lists(user=Depends(current_user),db:Session=Depends(get_db)):
    q=db.query(PackingList)
    rows=q.order_by(PackingList.id.desc()).all()
    if user["role"]!="admin":
        rows=[x for x in rows if can_access(x,user)]
    return [list_out(x) for x in rows]
@app.get("/lists/{list_id}")
def get_list(list_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
    l=db.get(PackingList,list_id)
    if not l or not can_access(l,user): raise HTTPException(404,"List not found")
    return list_out(l)
@app.put("/lists/{list_id}")
def update_list(list_id:int,data:ListUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    l=db.get(PackingList,list_id)
    if not l or not can_access(l,user): raise HTTPException(404,"List not found")
    if l.owner_id!=user["id"] and user["role"]!="admin": raise HTTPException(403,"Only owner can edit list")
    l.title=data.title; db.commit(); db.refresh(l); return list_out(l)
@app.delete("/lists/{list_id}")
def delete_list(list_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
    l=db.get(PackingList,list_id)
    if not l or not can_access(l,user): raise HTTPException(404,"List not found")
    if l.owner_id!=user["id"] and user["role"]!="admin": raise HTTPException(403,"Only owner can delete list")
    db.delete(l); db.commit(); return {"deleted":list_id}
@app.post("/lists/{list_id}/share")
def share_list(list_id:int,data:ShareIn,user=Depends(current_user),db:Session=Depends(get_db)):
    l=db.get(PackingList,list_id)
    if not l or l.owner_id!=user["id"]: raise HTTPException(404,"List not found or not owner")
    ids=set(json.loads(l.shared_with or "[]")); ids.add(data.user_id); l.shared_with=json.dumps(sorted(ids)); db.commit()
    return {"list_id":list_id,"shared_with":sorted(ids)}
@app.post("/lists/{list_id}/items",status_code=201)
def add_item(list_id:int,data:ItemIn,user=Depends(current_user),db:Session=Depends(get_db)):
    l=db.get(PackingList,list_id)
    if not l or not can_access(l,user): raise HTTPException(404,"List not found")
    if l.owner_id!=user["id"] and user["role"]!="admin": raise HTTPException(403,"Only owner can edit items")
    i=Item(list_id=list_id,**data.model_dump()); db.add(i); db.commit(); db.refresh(i); return item_out(i)
@app.put("/items/{item_id}")
def update_item(item_id:int,data:ItemUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Item,item_id); l=db.get(PackingList,i.list_id) if i else None
    if not i or not l or not can_access(l,user): raise HTTPException(404,"Item not found")
    if l.owner_id!=user["id"] and user["role"]!="admin": raise HTTPException(403,"Only owner can edit items")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(i,k,v)
    db.commit(); db.refresh(i); return item_out(i)
@app.delete("/items/{item_id}")
def delete_item(item_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
    i=db.get(Item,item_id); l=db.get(PackingList,i.list_id) if i else None
    if not i or not l or not can_access(l,user): raise HTTPException(404,"Item not found")
    if l.owner_id!=user["id"] and user["role"]!="admin": raise HTTPException(403,"Only owner can delete items")
    db.delete(i); db.commit(); return {"deleted":item_id}
@app.get("/lists/{list_id}/items")
def filter_items(list_id:int,category:str|None=Query(default=None),packed:bool|None=Query(default=None),user=Depends(current_user),db:Session=Depends(get_db)):
    l=db.get(PackingList,list_id)
    if not l or not can_access(l,user): raise HTTPException(404,"List not found")
    q=db.query(Item).filter(Item.list_id==list_id)
    if category: q=q.filter(Item.category==category)
    if packed is not None: q=q.filter(Item.is_packed==packed)
    return [item_out(x) for x in q.all()]
