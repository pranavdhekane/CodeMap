"""The engine: validate -> run algorithm -> check output -> save -> finish extras.

Algorithms never touch the database. They only turn input into output.
"""

import logging

from . import db
from .registry import get_algorithm
from .schemas import AlgorithmOutput
from .validation import ValidationError, validate_project_path

log = logging.getLogger("codemap.engine")

# Extra tasks that run after every run (success or failure). Each gets the run_id.
AFTER_RUN_HOOKS: list = []


def submit(
    algorithm_name: str, project_id: int, raw_input: dict, commit_hash: str | None = None
) -> tuple[int, dict]:
    """Validate the request and create a queued run.

    Returns (run_id, validated_input_dict). Raises KeyError for an unknown
    algorithm and ValidationError for bad input; nothing is saved in that case.
    """
    algo = get_algorithm(algorithm_name)  # KeyError if unknown
    if db.get_project(project_id) is None:
        raise ValidationError(f"Project {project_id} does not exist")
    try:
        data = algo.input_model.model_validate(raw_input)
    except Exception as error:
        raise ValidationError(f"Invalid input: {error}") from error
    data.project_path = validate_project_path(data.project_path)

    run_id = db.create_run(project_id, commit_hash)
    return run_id, data.model_dump()


def execute(run_id: int, algorithm_name: str, validated_input: dict) -> None:
    """Run the algorithm and save the result. Meant to run as a background task."""
    try:
        db.set_status(run_id, "running")
        algo = get_algorithm(algorithm_name)
        data = algo.input_model.model_validate(validated_input)

        result = algo.run(data)
        if isinstance(result, AlgorithmOutput):
            result = result.model_dump()
        output = AlgorithmOutput.model_validate(result)  # strict format check
        if output.algorithm != algo.name:
            raise ValueError("Output 'algorithm' does not match the algorithm name")

        db.save_results(run_id, output)
    except Exception:
        log.exception("Run %s failed", run_id)
        db.set_status(run_id, "failed")
    finally:
        for hook in AFTER_RUN_HOOKS:
            try:
                hook(run_id)
            except Exception:
                log.exception("After-run hook failed for run %s", run_id)


def run_now(
    algorithm_name: str, project_id: int, raw_input: dict, commit_hash: str | None = None
) -> int:
    """Submit and execute in one go (used by tests and the CLI)."""
    run_id, data = submit(algorithm_name, project_id, raw_input, commit_hash)
    execute(run_id, algorithm_name, data)
    return run_id
