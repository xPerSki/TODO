import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pymongo import MongoClient
from os import getenv
from bson import ObjectId
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging


DB_PASSWORD = getenv("DB_PASSWORD")
SECRET_CODE = getenv("KOD", "default")


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


def verify_code(request: Request):
    user_code = request.headers.get("Authorization")
    logging.warning(f"Received code: {user_code}")
    if user_code != SECRET_CODE:
        raise HTTPException(status_code=403, detail="Unauthorized")


@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/verify-code")
async def verify_code_api(data: dict):
    if "code" not in data or data["code"] != SECRET_CODE:
        raise HTTPException(status_code=401, detail="Invalid code")
    return {"message": "Access granted"}


@app.get("/tasks")
async def get_tasks(request: Request, authorized: bool = Depends(verify_code)):
    tasks = list(collection.find({}, {"_id": 1, "title": 1, "description": 1, "completed": 1}))
    for task in tasks:
        task["_id"] = str(task["_id"])
    return tasks


@app.post("/tasks")
async def create_task(request: Request, task: Task, authorized: bool = Depends(verify_code)):
    new_task = task.model_dump()
    result = collection.insert_one(new_task)
    return {"id": str(result.inserted_id), "message": "Task added"}


@app.delete("/tasks/{task_id}")
async def delete_task(request: Request, task_id: str, authorized: bool = Depends(verify_code)):
    result = collection.delete_one({"_id": ObjectId(task_id)})
    if result.deleted_count == 1:
        return {"message": "Task deleted"}
    return {"error": "Task not found"}


@app.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str, authorized: bool = Depends(verify_code)):
    task = collection.find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task["_id"] = str(task["_id"])
    return task


@app.put("/tasks/{task_id}")
async def update_task(request: Request, task_id: str, task: Task, authorized: bool = Depends(verify_code)):
    updated_task = task.model_dump()
    result = collection.update_one({"_id": ObjectId(task_id)}, {"$set": updated_task})
    if result.matched_count == 1:
        return {"message": "Task updated"}
    return {"error": "Task not found"}


@app.put("/tasks/{task_id}/toggle")
async def toggle_task(request: Request, task_id: str, authorized: bool = Depends(verify_code)):
    task = collection.find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_status = not task["completed"]
    collection.update_one({"_id": ObjectId(task_id)}, {"$set": {"completed": new_status}})
    return {"message": "Task status toggled", "completed": new_status}


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)
