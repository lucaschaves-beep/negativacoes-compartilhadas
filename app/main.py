from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.webhook import router as webhook_router
from app.api.search import router as search_router
from app.api.grupos import router as grupos_router
import os

app = FastAPI(
    title="Negativações Compartilhadas",
    description="IA para análise e cruzamento de evidências de negativação no Pipefy",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router, tags=["webhook"])
app.include_router(search_router, tags=["busca"])
app.include_router(grupos_router)

# Serve o frontend HTML
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/health")
async def health():
    return {"status": "ok", "service": "negativacoes-compartilhadas"}
