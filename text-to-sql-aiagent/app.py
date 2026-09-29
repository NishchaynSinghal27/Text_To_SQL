from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="Text-to-SQL RAG API")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "https://text-to-sql-aiagent.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def health_check():
    return {"status": "ok"}