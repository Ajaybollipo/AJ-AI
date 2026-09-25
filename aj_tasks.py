import uuid
from datetime import datetime


# ============================================================
# AJ 3.0 — AUTONOMOUS TASK ENGINE
# ============================================================

MAX_STEPS = 20
MAX_STEP_LENGTH = 2000
MAX_RESULT_LENGTH = 5000


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _clean_text(value, limit=MAX_STEP_LENGTH):
    return str(value or "").strip()[:limit]


def create_task(title, steps):
    """
    Create a structured task.

    The task engine tracks and executes only safe, explicitly
    supported operations. Sensitive external actions require
    confirmation before execution.
    """
    title = _clean_text(title, 300)

    if not title:
        title = "AJ Task"

    if not isinstance(steps, list):
        steps = []

    cleaned_steps = []

    for step in steps[:MAX_STEPS]:
        if isinstance(step, dict):
            description = _clean_text(step.get("description"))
        else:
            description = _clean_text(step)

        if description:
            cleaned_steps.append({
                "id": len(cleaned_steps) + 1,
                "description": description,
                "status": "pending",
                "result": None,
                "error": None,
                "requires_confirmation": requires_confirmation(
                    description
                )
            })

    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
        "current_step": 0,
        "steps": cleaned_steps,
        "result": None
    }


def get_progress(task):
    if not task:
        return {
            "status": "unknown",
            "completed": 0,
            "total": 0,
            "percent": 0
        }

    steps = task.get("steps", [])

    completed = sum(
        1
        for step in steps
        if step.get("status") == "completed"
    )

    total = len(steps)

    percent = (
        int((completed / total) * 100)
        if total
        else 0
    )

    return {
        "status": task.get("status", "unknown"),
        "completed": completed,
        "total": total,
        "percent": percent
    }


def start_task(task):
    """Start a task and prepare its first executable step."""
    if not task:
        return None

    if not task.get("steps"):
        task["status"] = "completed"
        task["result"] = "No steps were required."
        task["updated_at"] = _now()
        return task

    task["status"] = "running"
    task["updated_at"] = _now()

    # Do not automatically execute sensitive steps.
    start_next_step(task)

    return task


def start_next_step(task):
    """
    Find the next pending step.

    Sensitive steps are moved to waiting_confirmation instead
    of being started automatically.
    """
    if not task:
        return None

    for step in task.get("steps", []):
        if step.get("status") != "pending":
            continue

        if step.get("requires_confirmation"):
            step["status"] = "waiting_confirmation"
            task["current_step"] = step["id"]
            task["status"] = "waiting_confirmation"
            task["updated_at"] = _now()
            return step

        step["status"] = "running"
        task["current_step"] = step["id"]
        task["status"] = "running"
        task["updated_at"] = _now()

        return step

    _finish_if_complete(task)

    return None


def confirm_current_step(task):
    """
    Explicitly approve the current sensitive step.

    This function only changes its state to running.
    A separate executor must perform the actual action.
    """
    if not task:
        return None

    current_id = task.get("current_step")

    for step in task.get("steps", []):
        if step.get("id") == current_id:
            if step.get("status") != "waiting_confirmation":
                return step

            step["status"] = "running"
            task["status"] = "running"
            task["updated_at"] = _now()

            return step

    return None


def complete_step(task, step_id, result=""):
    """Complete a running step and prepare the next step."""
    if not task:
        return False

    for step in task.get("steps", []):
        if step.get("id") != step_id:
            continue

        if step.get("status") not in {
            "running",
            "waiting_confirmation"
        }:
            return False

        step["status"] = "completed"
        step["result"] = _clean_text(
            result,
            MAX_RESULT_LENGTH
        )
        step["error"] = None
        task["updated_at"] = _now()

        _finish_if_complete(task)

        return True

    return False


def fail_step(task, step_id, error):
    """Fail the current step and stop the task."""
    if not task:
        return False

    for step in task.get("steps", []):
        if step.get("id") != step_id:
            continue

        step["status"] = "failed"
        step["error"] = _clean_text(error, 2000)
        task["status"] = "failed"
        task["updated_at"] = _now()

        return True

    return False


def skip_step(task, step_id, reason="Skipped"):
    """Skip a step without performing it."""
    if not task:
        return False

    for step in task.get("steps", []):
        if step.get("id") != step_id:
            continue

        step["status"] = "skipped"
        step["result"] = _clean_text(reason, 2000)
        task["updated_at"] = _now()

        _finish_if_complete(task)

        return True

    return False


def cancel_task(task):
    """Cancel a task before completion."""
    if not task:
        return False

    if task.get("status") == "completed":
        return False

    task["status"] = "cancelled"
    task["updated_at"] = _now()

    return True


def _finish_if_complete(task):
    steps = task.get("steps", [])

    if not steps:
        task["status"] = "completed"
        task["current_step"] = 0
        task["result"] = "Task completed."
        task["updated_at"] = _now()
        return

    if any(
        step.get("status") in {
            "failed",
            "waiting_confirmation",
            "running",
            "pending"
        }
        for step in steps
    ):
        return

    if all(
        step.get("status") in {"completed", "skipped"}
        for step in steps
    ):
        task["status"] = "completed"
        task["result"] = _build_final_result(task)
        task["current_step"] = len(steps)
        task["updated_at"] = _now()


def _build_final_result(task):
    results = []

    for step in task.get("steps", []):
        result = step.get("result")

        if result:
            results.append(
                f"Step {step.get('id')}: {result}"
            )

    if not results:
        return "Task completed."

    return "\n\n".join(results)[:MAX_RESULT_LENGTH]


def task_summary(task):
    if not task:
        return "No task is active."

    progress = get_progress(task)

    lines = [
        f"Task: {task.get('title', 'AJ Task')}",
        f"Status: {progress['status'].upper()}",
        f"Progress: {progress['completed']}/"
        f"{progress['total']} ({progress['percent']}%)"
    ]

    for step in task.get("steps", []):
        status = step.get("status", "pending").upper()

        suffix = ""

        if step.get("requires_confirmation"):
            suffix = " — CONFIRMATION REQUIRED"

        lines.append(
            f"{step.get('id')}. [{status}] "
            f"{step.get('description', '')}{suffix}"
        )

    return "\n".join(lines)


def is_sensitive_action(description):
    """
    Detect actions that require explicit confirmation.

    This is a safety gate, not an executor.
    """
    text = _clean_text(description, 500).lower()

    sensitive_terms = (
        "delete",
        "purchase",
        "buy",
        "pay",
        "transfer money",
        "send money",
        "send email",
        "send message",
        "post publicly",
        "publish",
        "change password",
        "close account",
        "submit application",
        "place order",
        "book appointment",
        "make reservation"
    )

    return any(
        term in text
        for term in sensitive_terms
    )


def requires_confirmation(description):
    return is_sensitive_action(description)


def get_current_step(task):
    """Return the currently active/waiting step."""
    if not task:
        return None

    current_id = task.get("current_step")

    for step in task.get("steps", []):
        if step.get("id") == current_id:
            return step

    return None


def get_next_executable_step(task):
    """
    Return the next step that can be safely executed.

    Sensitive steps remain blocked until explicitly confirmed.
    """
    if not task:
        return None

    for step in task.get("steps", []):
        if step.get("status") == "pending":
            if step.get("requires_confirmation"):
                return None

            return step

    return None


def task_to_dict(task):
    """Return a safe representation suitable for an API response."""
    if not task:
        return None

    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "status": task.get("status"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "current_step": task.get("current_step"),
        "steps": [
            {
                "id": step.get("id"),
                "description": step.get("description"),
                "status": step.get("status"),
                "result": step.get("result"),
                "error": step.get("error"),
                "requires_confirmation": step.get(
                    "requires_confirmation",
                    False
                )
            }
            for step in task.get("steps", [])
        ],
        "result": task.get("result"),
        "progress": get_progress(task)
    }
