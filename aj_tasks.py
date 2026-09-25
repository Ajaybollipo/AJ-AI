import uuid
from datetime import datetime


# ============================================================
# AJ 3.0 — AUTONOMOUS TASK ENGINE
# ============================================================

MAX_STEPS = 20
MAX_STEP_LENGTH = 2000


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _clean_text(value, limit=MAX_STEP_LENGTH):
    return str(value or "").strip()[:limit]


def create_task(title, steps):
    """
    Create a safe, structured task.

    The engine only creates and tracks tasks here.
    It does not automatically perform sensitive external actions.
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
                "error": None
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
    """Return a compact progress description."""
    if not task:
        return {
            "status": "unknown",
            "completed": 0,
            "total": 0,
            "percent": 0
        }

    steps = task.get("steps", [])

    completed = sum(
        1 for step in steps
        if step.get("status") == "completed"
    )

    total = len(steps)

    percent = int(
        (completed / total) * 100
    ) if total else 0

    return {
        "status": task.get("status", "unknown"),
        "completed": completed,
        "total": total,
        "percent": percent
    }


def start_task(task):
    """Move a pending task into execution."""
    if not task:
        return None

    if not task.get("steps"):
        task["status"] = "completed"
        task["result"] = "No steps were required."
        task["updated_at"] = _now()
        return task

    task["status"] = "running"
    task["current_step"] = 1
    task["updated_at"] = _now()

    return task


def start_next_step(task):
    """Start the next pending task step."""
    if not task:
        return None

    for step in task.get("steps", []):
        if step.get("status") == "pending":
            step["status"] = "running"
            task["current_step"] = step["id"]
            task["status"] = "running"
            task["updated_at"] = _now()
            return step

    return None


def complete_step(task, step_id, result=""):
    """Mark one task step as completed."""
    if not task:
        return False

    for step in task.get("steps", []):
        if step.get("id") == step_id:
            step["status"] = "completed"
            step["result"] = _clean_text(result, 5000)
            step["error"] = None
            task["updated_at"] = _now()

            if all(
                item.get("status") == "completed"
                for item in task.get("steps", [])
            ):
                task["status"] = "completed"
                task["result"] = _build_final_result(task)
                task["current_step"] = len(task.get("steps", []))

            return True

    return False


def fail_step(task, step_id, error):
    """Mark one task step as failed."""
    if not task:
        return False

    for step in task.get("steps", []):
        if step.get("id") == step_id:
            step["status"] = "failed"
            step["error"] = _clean_text(error, 2000)
            task["status"] = "failed"
            task["updated_at"] = _now()
            return True

    return False


def skip_step(task, step_id, reason="Skipped"):
    """Safely skip a task step."""
    if not task:
        return False

    for step in task.get("steps", []):
        if step.get("id") == step_id:
            step["status"] = "skipped"
            step["result"] = _clean_text(reason, 2000)
            task["updated_at"] = _now()
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


def _build_final_result(task):
    """Combine completed step results into one final result."""
    results = []

    for step in task.get("steps", []):
        result = step.get("result")

        if result:
            results.append(
                f"Step {step.get('id')}: {result}"
            )

    if not results:
        return "Task completed."

    return "\n\n".join(results)


def task_summary(task):
    """Return a human-readable task summary."""
    if not task:
        return "No task is active."

    progress = get_progress(task)

    lines = [
        f"Task: {task.get('title', 'AJ Task')}",
        f"Status: {progress['status'].upper()}",
        f"Progress: {progress['completed']}/{progress['total']} "
        f"({progress['percent']}%)"
    ]

    for step in task.get("steps", []):
        status = step.get("status", "pending").upper()
        lines.append(
            f"{step.get('id')}. [{status}] "
            f"{step.get('description', '')}"
        )

    return "\n".join(lines)


def is_sensitive_action(description):
    """
    Detect actions that should require explicit confirmation
    before a future executor is allowed to perform them.
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
        "post publicly",
        "publish",
        "change password",
        "close account",
        "submit application"
    )

    return any(term in text for term in sensitive_terms)


def requires_confirmation(description):
    return is_sensitive_action(description)


def task_to_dict(task):
    """Return a safe copy suitable for an API response."""
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
                "error": step.get("error")
            }
            for step in task.get("steps", [])
        ],
        "result": task.get("result"),
        "progress": get_progress(task)
    }
