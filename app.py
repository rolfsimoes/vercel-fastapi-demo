# A small FastAPI app. Vercel runs it, and serves the page in the public/ folder.
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Put the docs under /api, so all the app lives under /api.
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")


# GET /api/hello?name=Ana
@app.get("/api/hello")
def hello(name: str = "mundo"):
    return {"message": f"Olá, {name}!"}


# The body of POST /api/average, for example {"grades": [7, 8, 9]}
class Grades(BaseModel):
    grades: list[float]


# POST /api/average
@app.post("/api/average")
def average(data: Grades):
    if len(data.grades) == 0:
        raise HTTPException(status_code=422, detail="Envie pelo menos uma nota.")

    for grade in data.grades:
        if grade < 0 or grade > 10:
            raise HTTPException(status_code=422, detail="Cada nota vai de 0 a 10.")

    result = sum(data.grades) / len(data.grades)
    passed = result >= 7
    return {"average": round(result, 2), "passed": passed}
