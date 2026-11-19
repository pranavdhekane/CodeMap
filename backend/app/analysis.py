"""API endpoints for projects and for running algorithms through the engine."""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..core import analyzers  # noqa: F401  (imports every algorithm so they register)
from ..core import engine
from ..core.engine import db
from .auth import bearer_token, current_user
from .config import is_local_mode

router = APIRouter(prefix="/api")
db.init_db()


class ProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    repo_url: str | None = None


class AnalyzeRequest(BaseModel):
    algorithm: str
    project_id: int
    project_path: str
    commit_hash: str | None = None
    options: dict = Field(default_factory=dict)


def request_user(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """Local mode has no login; cloud mode validates the Supabase token."""
    if is_local_mode():
        return {"id": "local-user"}
    return current_user(bearer_token(authorization))


User = Annotated[dict[str, Any], Depends(request_user)]


@router.get("/algorithms")
def algorithms() -> dict[str, Any]:
    """List the algorithms the engine can run."""
    return {"algorithms": engine.list_algorithms()}


@router.post("/projects", status_code=201)
def create_project(body: ProjectRequest, user: User) -> dict[str, Any]:
    project_id = db.create_project(body.name, body.description, body.repo_url)
    return db.get_project(project_id)


@router.get("/projects")
def list_projects(user: User) -> dict[str, Any]:
    return {"projects": db.list_projects()}


@router.post("/analyze", status_code=202)
def analyze(
    body: AnalyzeRequest, background_tasks: BackgroundTasks, user: User
) -> dict[str, Any]:
    """Validate the request, queue a run, and process it in the background."""
    raw_input = {"project_path": body.project_path, "options": body.options}
    try:
        run_id, data = engine.submit(
            body.algorithm, body.project_id, raw_input, body.commit_hash
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except engine.ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    background_tasks.add_task(engine.execute, run_id, body.algorithm, data)
    return {"run_id": run_id, "status": "queued"}


@router.get("/runs/{run_id}")
def get_run(run_id: int, user: User) -> dict[str, Any]:
    """Return the status and results of one run."""
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
