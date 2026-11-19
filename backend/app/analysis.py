"""API endpoints for projects and for running algorithms through the engine."""

import io
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
    status,
)
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
    token = bearer_token(authorization)
    if token == "local-token":
        return {"id": "local-user"}
    return current_user(token)


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


@router.get("/projects/{project_id}")
def get_project(project_id: int, user: User) -> dict[str, Any]:
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, user: User) -> Response:
    deleted = db.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/projects/upload", status_code=201)
async def upload_project_zip(
    file: UploadFile = File(...),
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    algorithm: Annotated[str, Form()] = "basic_algo_1",
    user: User = None,
) -> dict[str, Any]:
    """Upload a project archive as a .zip, analyze its AST, and store ONLY the analysis.
    
    The code is extracted into a temporary directory, analyzed, and immediately deleted.
    """
    filename = file.filename or "project.zip"
    if not (
        filename.lower().endswith(".zip")
        or file.content_type in ("application/zip", "application/x-zip-compressed", "multipart/form-data")
    ):
        raise HTTPException(status_code=400, detail="Only .zip files are supported")

    proj_name = name.strip() if name and name.strip() else Path(filename).stem
    if not proj_name:
        proj_name = "unnamed-project"

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded archive is empty")

    # 1. Create the project record
    project_id = db.create_project(proj_name, description, None)

    # 2. Extract into a temporary directory, run analysis, and delete temporary folder
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                target_base = os.path.abspath(temp_dir)
                for member in zf.namelist():
                    dest = os.path.abspath(os.path.join(temp_dir, member))
                    if not (dest == target_base or dest.startswith(target_base + os.sep)):
                        raise HTTPException(
                            status_code=400,
                            detail="Zip archive contains unsafe relative paths",
                        )
                zf.extractall(temp_dir)
        except zipfile.BadZipFile as err:
            raise HTTPException(status_code=400, detail="Invalid zip file archive") from err

        # If archive unzips to a single root directory (e.g. repo-main/), point analysis to that
        entries = [
            os.path.join(temp_dir, e)
            for e in os.listdir(temp_dir)
            if not e.startswith("__MACOSX") and not e.startswith(".")
        ]
        target_path = temp_dir
        if len(entries) == 1 and os.path.isdir(entries[0]):
            target_path = entries[0]

        # Run analysis synchronously while temp_dir is alive
        try:
            engine.run_now(algorithm, project_id, {"project_path": target_path})
        except Exception as err:
            # Clean up the project on unrecoverable failure
            db.delete_project(project_id)
            raise HTTPException(status_code=422, detail=f"Analysis failed: {err}") from err

    # The temp_dir is deleted; return project with persisted analysis summary
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created project")
    return project


@router.post("/projects/seed-demo", status_code=201)
def seed_demo_project(user: User) -> dict[str, Any]:
    """Analyzes a built-in sample project and persists its analysis for instant exploration."""
    demo_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "Main_Algo_draft", "tests", "fixtures", "seeded_project"
    )
    if not os.path.isdir(demo_path):
        demo_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")

    proj_id = db.create_project(
        name="shop-billing-system",
        description="Demo eCommerce architecture with payment cycles, caching, and recursion",
        repo_url=None,
    )
    engine.run_now("basic_algo_1", proj_id, {"project_path": os.path.abspath(demo_path)})
    project = db.get_project(proj_id)
    if project is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve seeded project")
    return project


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
