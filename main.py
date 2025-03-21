import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pymongo import MongoClient
from os import getenv
from bson import ObjectId
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets


DB_PASSWORD = getenv("DB_PASSWORD")
uri = f"mongodb+srv://persky:{DB_PASSWORD}@cluster0.jevvu.mongodb.net/?appName=Cluster0"

client = MongoClient(uri)
db = client["todo_db"]
collection = db["tasks"]

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://xperski.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
templates = Jinja2Templates(directory="templates")


class Task(BaseModel):
    title: str
    description: str
    completed: bool = False


@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

active_sessions = {}
security = HTTPBasic()


@app.post("/login")
async def login(credentials: HTTPBasicCredentials = Depends(security)):
    user = db.users.find_one({"username": credentials.username, "password": credentials.password})
    if user:
        session_token = secrets.token_hex(16)
        active_sessions[session_token] = credentials.username
        return {"token": session_token}
    raise HTTPException(status_code=401, detail="Niepoprawne dane logowania")


@app.get("/tasks")
async def get_tasks(request: Request):
    token = request.headers.get("Authorization")
    if not token or token not in active_sessions:
        raise HTTPException(status_code=403, detail="Brak dostępu")

    tasks = list(collection.find({}, {"_id": 1, "title": 1, "description": 1, "completed": 1}))
    for task in tasks:
        task["_id"] = str(task["_id"])
    return tasks


@app.post("/tasks")
async def create_task(task: Task):
    new_task = task.model_dump()
    result = collection.insert_one(new_task)
    return {"id": str(result.inserted_id), "message": "Task added"}


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    result = collection.delete_one({"_id": ObjectId(task_id)})
    if result.deleted_count == 1:
        return {"message": "Task deleted"}
    return {"error": "Task not found"}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = collection.find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task["_id"] = str(task["_id"])
    return task


@app.put("/tasks/{task_id}")
async def update_task(task_id: str, task: Task):
    updated_task = task.model_dump()
    result = collection.update_one({"_id": ObjectId(task_id)}, {"$set": updated_task})
    if result.matched_count == 1:
        return {"message": "Task updated"}
    return {"error": "Task not found"}


@app.put("/tasks/{task_id}/toggle")
async def toggle_task(task_id: str):
    task = collection.find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_status = not task["completed"]
    collection.update_one({"_id": ObjectId(task_id)}, {"$set": {"completed": new_status}})
    return {"message": "Task status toggled", "completed": new_status}


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)
