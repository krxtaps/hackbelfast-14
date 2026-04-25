from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from maps.loader import load_botanic_streets

app = FastAPI()

app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/streets/botanic")
def get_botanic_streets():
    data = load_botanic_streets()
    if not data:
        raise HTTPException(status_code=404, detail="Botanic streets data not found")
    return data
