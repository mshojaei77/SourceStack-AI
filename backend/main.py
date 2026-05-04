import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.api.chat import router as chat_router
from backend.api.exports import router as exports_router
from backend.api.reports import router as reports_router
from backend.api.settings import router as settings_router
from backend.api.sources import router as sources_router
from backend.api.workbases import router as workbases_router


app = FastAPI(title="SourceStack AI API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sourcestack-api"}


app.include_router(workbases_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(exports_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
