from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator, HTTPException
from pydantic import BaseModel, Field
app=FastAPI(title="TripPack Categorization Service",version="1.0.0")
Instrumentator().instrument(app).expose(app)
CATEGORIES=[
 {"name":"одяг","description":"Одяг і взуття"},
 {"name":"техніка","description":"Електроніка та аксесуари"},
 {"name":"документи","description":"Паспорт, квитки, страхування"},
 {"name":"гігієна","description":"Засоби особистої гігієни"},
 {"name":"аптечка","description":"Ліки та засоби першої допомоги"},
 {"name":"інше","description":"Інші речі"}
]
SUGGESTIONS={
 "відпочинок":[("Футболки","одяг"),("Шорти","одяг"),("Купальник","одяг"),("Сонцезахисний крем","гігієна"),("Паспорт","документи"),("Зарядний пристрій","техніка")],
 "ділова":[("Діловий одяг","одяг"),("Ноутбук","техніка"),("Зарядний пристрій","техніка"),("Паспорт або ID","документи"),("Документи зустрічей","документи"),("Засоби гігієни","гігієна")],
 "похід":[("Термобілизна","одяг"),("Трекінгове взуття","одяг"),("Ліхтарик","техніка"),("Аптечка","аптечка"),("Пляшка для води","інше"),("Паспорт","документи")]
}
class CategoryIn(BaseModel):
 name:str=Field(min_length=2,max_length=50)
 description:str=""
@app.get("/health")
def health(): return {"status":"ok","service":"categorization-service"}
@app.get("/categories")
def categories(): return CATEGORIES
@app.get("/trip-types")
def trip_types(): return [{"id":k,"name":k} for k in SUGGESTIONS]
@app.get("/suggestions/{trip_type}")
def suggestions(trip_type:str):
 key=trip_type.lower()
 if key not in SUGGESTIONS: raise HTTPException(404,"Unknown trip type. Use: відпочинок, ділова, похід")
 return [{"name":n,"category":c,"quantity":1} for n,c in SUGGESTIONS[key]]
@app.get("/classify")
def classify(name:str):
 text=name.lower()
 rules={"документи":["паспорт","квиток","страх","id","віза"],"техніка":["телефон","ноутбук","заряд","навуш","камера","ліхтар"],"гігієна":["шампун","зуб","крем","щітка","дезодорант"],"аптечка":["ліки","таблет","аптеч","пластир"],"одяг":["футбол","штани","шорт","куртк","взут","шкарп","сукня","білизн"]}
 for category,words in rules.items():
  if any(w in text for w in words): return {"name":name,"category":category}
 return {"name":name,"category":"інше"}
