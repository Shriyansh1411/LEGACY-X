from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analysis import router as analysis_router
from app.api.routes.explain import router as explain_router
from app.api.routes.generation import router as generation_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.understand import router as understand_router
from app.api.routes.verification import router as verification_router
from app.api.routes.execute import router as execute_router
from app.api.routes.behavior_graph import router as behavior_graph_router
from app.db.database import initialize_database
from app.models.project import ProjectRecord  # noqa: F401

app = FastAPI(title="LEGACY-X", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

initialize_database()

app.include_router(health_router)
app.include_router(projects_router)
app.include_router(analysis_router)
app.include_router(understand_router)
app.include_router(generation_router)
app.include_router(verification_router)
app.include_router(execute_router)
app.include_router(explain_router)
app.include_router(behavior_graph_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
