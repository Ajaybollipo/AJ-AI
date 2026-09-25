from flask import Flask, jsonify, request, send_file, send_from_directory
from datetime import datetime
from werkzeug.utils import secure_filename
from collections import defaultdict, deque
import os
import tempfile
import time
import requests

from aj_brain import ask_aj
from aj_files import prepare_file_for_ai
from aj_voice import process_voice_command
from aj_tasks import (
    get_task,
    get_all_tasks,
    save_task,
    start_task,
    start_next_step,
    confirm_current_step,
    cancel_task,
    task_to_dict,
    task_summary,
)


app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)

# =========================================================
# CONFIGURATION / SECURITY
# =========================================================

app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

# Production security headers.
# Compatible with the current AJ interface and browser speech APIs.
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "microphone=(self), camera=(), geolocation=()"
    )
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


MAX_MESSAGE_LENGTH = 6000
MAX_HISTORY_ITEMS = 20
MAX_HISTORY_ITEM_LENGTH = 12000
MAX_FILE_CONTENT_LENGTH = 50000

ALLOWED_FILE_EXTENSIONS = {
    "txt", "md", "py", "js", "html", "css", "json", "csv",
    "xml", "java", "c", "cpp", "sql", "pdf"
}

RATE_LIMITS = {
    "command": (30, 60),
    "voice": (30, 60),
    "upload": (10, 60),
    "file_question": (20, 60)
}

_request_log = defaultdict(deque)

# File-question endpoint uses OpenRouter directly.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"


def get_client_ip():
    # Do not trust arbitrary X-Forwarded-For values.
    return request.remote_addr or "unknown"


def rate_limited(name):
    limit, window = RATE_LIMITS[name]
    now = time.time()
    ip = get_client_ip()
    key = f"{name}:{ip}"

    bucket = _request_log[key]

    while bucket and now - bucket[0] > window:
        bucket.popleft()

    if len(bucket) >= limit:
        return True

    bucket.append(now)
    return False


def security_error(message, status=400):
    return jsonify({
        "assistant": "AJ",
        "response": message,
        "state": "ERROR"
    }), status


def clean_history(history):
    if not isinstance(history, list):
        return []

    cleaned = []

    for item in history[-MAX_HISTORY_ITEMS:]:
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()

        if role not in {"user", "assistant", "system"}:
            continue

        if not content:
            continue

        cleaned.append({
            "role": role,
            "content": content[:MAX_HISTORY_ITEM_LENGTH]
        })

    return cleaned


def allowed_file(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_FILE_EXTENSIONS


def openrouter_headers():
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Ajaybollipo/AJ-AI",
        "X-Title": "AJ Personal AI Assistant"
    }


# =========================================================
# AJ STATUS
# =========================================================

AJ_STATUS = {
    "state": "ONLINE",
    "message": "AJ is ready.",
    "updated": datetime.now().strftime("%H:%M:%S")
}


def set_status(state, message):
    AJ_STATUS["state"] = state
    AJ_STATUS["message"] = message
    AJ_STATUS["updated"] = datetime.now().strftime("%H:%M:%S")


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return send_file(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "index.html"
        )
    )


# =========================================================
# SIGNATURE / STATIC IMAGES
# =========================================================

@app.route("/static/images/<path:filename>")
def signature(filename):
    static_directory = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static",
        "images"
    )

    return send_from_directory(
        static_directory,
        filename
    )


# =========================================================
# STATUS API
# =========================================================

@app.route("/api/status")
def status():
    return jsonify({
        "assistant": "AJ",
        "state": AJ_STATUS["state"],
        "message": AJ_STATUS["message"],
        "time": AJ_STATUS["updated"]
    })


# =========================================================
# VOICE COMMAND API
# =========================================================

@app.route("/api/voice", methods=["POST"])
def voice_command():
    if rate_limited("voice"):
        return security_error(
            "Too many voice requests. Please wait a moment.",
            429
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return security_error("Invalid request format.", 400)

    message = str(data.get("message", "")).strip()

    # IMPORTANT FIX:
    # Voice now receives and sanitizes the same conversation history
    # used by the normal command endpoint.
    history = clean_history(
        data.get("history", [])
    )

    if not message:
        return jsonify({
            "assistant": "AJ",
            "response": "I didn't hear a command.",
            "state": "ONLINE"
        }), 400

    if len(message) > MAX_MESSAGE_LENGTH:
        return security_error(
            "Your voice command is too long. Please shorten it.",
            400
        )

    try:
        result = process_voice_command(message)

        command = result.get("command", message)

        if not command:
            return jsonify({
                "assistant": "AJ",
                "response": "Yes, Ajay?",
                "wake_word": result.get("wake_word", False),
                "state": "LISTENING"
            })

        set_status(
            "THINKING",
            "Processing voice command..."
        )

        # Pass the sanitized conversation history to AJ.
        # Define it here as well so the deployed voice handler
        # always has a local history variable.
        voice_history = clean_history(
            data.get("history", [])
        )

        response = ask_aj(
            command,
            voice_history
        )

        set_status(
            "ONLINE",
            "AJ is ready."
        )

        return jsonify({
            "assistant": "AJ",
            "response": response,
            "command": command,
            "wake_word": result.get("wake_word", False),
            "state": "ONLINE"
        })

    except Exception as error:
        print("VOICE COMMAND ERROR:", error)

        set_status(
            "ERROR",
            "AJ voice command failed."
        )

        return jsonify({
            "assistant": "AJ",
            "response": "I couldn't process that voice command.",
            "state": "ERROR"
        }), 500


# =========================================================
# COMMAND API
# =========================================================

@app.route("/api/command", methods=["POST"])
def command():
    if rate_limited("command"):
        return security_error(
            "Too many requests. Please wait a moment.",
            429
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return security_error("Invalid request format.", 400)

    message = str(data.get("message", "")).strip()
    history = clean_history(data.get("history", []))

    if not message:
        return jsonify({
            "assistant": "AJ",
            "response": "Please say something.",
            "state": "ONLINE"
        }), 400

    if len(message) > MAX_MESSAGE_LENGTH:
        return security_error(
            "Your message is too long. Please shorten it.",
            400
        )

    try:
        lower = message.lower()

        set_status(
            "THINKING",
            "Understanding your request..."
        )

        if any(word in lower for word in [
            "search",
            "look up",
            "find information",
            "find info",
            "google",
            "latest",
            "current",
            "news"
        ]):
            set_status(
                "SEARCHING",
                "Searching..."
            )

        elif any(word in lower for word in [
            "open",
            "launch",
            "start",
            "play",
            "go to",
            "take me",
            "calculate",
            "weather"
        ]):
            set_status(
                "EXECUTING",
                "Executing command..."
            )

        response = ask_aj(
            message,
            history
        )

        set_status(
            "ONLINE",
            "AJ is ready."
        )

        return jsonify({
            "assistant": "AJ",
            "response": response,
            "state": "ONLINE"
        })

    except Exception as error:
        print("COMMAND ERROR:", error)

        set_status(
            "ERROR",
            "AJ encountered an error."
        )

        return jsonify({
            "assistant": "AJ",
            "response": "I'm having trouble processing that right now.",
            "state": "ERROR"
        }), 500


# =========================================================
# FILE INTELLIGENCE
# =========================================================

@app.route("/api/upload", methods=["POST"])
def upload_file():
    if rate_limited("upload"):
        return security_error(
            "Too many file uploads. Please wait a moment.",
            429
        )

    if "file" not in request.files:
        return security_error(
            "No file was uploaded.",
            400
        )

    uploaded_file = request.files["file"]

    if not uploaded_file.filename:
        return security_error(
            "Please select a file.",
            400
        )

    if len(uploaded_file.filename) > 255:
        return security_error(
            "File name is too long.",
            400
        )

    if not allowed_file(uploaded_file.filename):
        return security_error(
            "That file type is not supported.",
            400
        )

    safe_filename = secure_filename(uploaded_file.filename)

    if not safe_filename:
        return security_error(
            "Invalid file name.",
            400
        )

    temporary_path = None

    try:
        set_status(
            "READING",
            "Reading your file..."
        )

        suffix = os.path.splitext(safe_filename)[1].lower()

        # Extra size protection even though Flask has a global limit.
        uploaded_file.stream.seek(0, os.SEEK_END)
        size = uploaded_file.stream.tell()
        uploaded_file.stream.seek(0)

        if size > 5 * 1024 * 1024:
            return security_error(
                "File is too large. Maximum allowed size is 5 MB.",
                400
            )

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temporary_file:
            uploaded_file.save(temporary_file.name)
            temporary_path = temporary_file.name

        result = prepare_file_for_ai(temporary_path)

        if not result.get("success"):
            set_status(
                "ONLINE",
                "AJ is ready."
            )

            return jsonify({
                "assistant": "AJ",
                "response": result.get(
                    "error",
                    "AJ could not read the file."
                ),
                "state": "ERROR"
            }), 400

        file_name = result.get(
            "name",
            safe_filename
        )

        content = str(
            result.get("content", "")
        )

        truncated = result.get(
            "truncated",
            False
        )

        content = content[:MAX_FILE_CONTENT_LENGTH]

        analysis_prompt = f"""
You are AJ, a personal AI assistant.

The user uploaded this file:

FILE NAME:
{file_name}

FILE CONTENT:
{content}

Analyze the uploaded file carefully.

IMPORTANT FILE INTELLIGENCE RULES:
- Treat the uploaded file as the primary source for file-related questions.
- Answer questions about the file using the actual file content.
- If the answer is not supported by the file, clearly say that it is not found in the uploaded file.
- Do not silently replace file content with general knowledge.

If it is code:
- Explain what it does.
- Identify important sections.
- Point out obvious errors if present.
- Suggest useful improvements.

If it is a document:
- Summarize the important information.
- Identify key points.
- Answer questions using the document.

Do not invent information that is not present in the file.
"""

        response = ask_aj(
            analysis_prompt,
            []
        )

        if truncated:
            response += (
                "\n\nNote: The file was large, so AJ analyzed "
                "the available extracted content."
            )

        set_status(
            "ONLINE",
            "AJ is ready."
        )

        return jsonify({
            "assistant": "AJ",
            "response": response,
            "filename": file_name,
            "state": "ONLINE"
        })

    except Exception as error:
        print("FILE UPLOAD ERROR:", error)

        set_status(
            "ERROR",
            "AJ could not read the file."
        )

        return jsonify({
            "assistant": "AJ",
            "response": "AJ could not process that file.",
            "state": "ERROR"
        }), 500

    finally:
        if temporary_path:
            try:
                os.remove(temporary_path)
            except Exception:
                pass


# =========================================================
# FILE QUESTION API
# =========================================================

@app.route("/api/file-question", methods=["POST"])
def file_question():
    if rate_limited("file_question"):
        return security_error(
            "Too many file questions. Please wait a moment.",
            429
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return security_error("Invalid request format.", 400)

    question = str(
        data.get("question", "")
    ).strip()

    content = str(
        data.get("content", "")
    )

    file_name = str(
        data.get("filename", "uploaded file")
    )

    if not question:
        return security_error(
            "Please ask a question about the file.",
            400
        )

    if len(question) > MAX_MESSAGE_LENGTH:
        return security_error(
            "Your file question is too long.",
            400
        )

    if not content:
        return security_error(
            "No file content was provided.",
            400
        )

    content = content[:MAX_FILE_CONTENT_LENGTH]

    if not OPENROUTER_API_KEY:
        return jsonify({
            "assistant": "AJ",
            "response": "OpenRouter API key is not connected.",
            "state": "ERROR"
        }), 500

    try:
        set_status(
            "THINKING",
            "Answering from your file..."
        )

        prompt = f"""
You are AJ File Intelligence.

The user uploaded a file named:
{file_name}

FILE CONTENT:
{content}

USER QUESTION:
{question}

Answer the user's question using the uploaded file as the
primary source.

Rules:
- Use only information supported by the file.
- Do not invent information.
- If the answer is not present or cannot be determined from
  the file, say so clearly.
- If the file contains code, refer to the relevant code section.
- Keep the answer clear and useful.
"""

        response = requests.post(
            OPENROUTER_URL,
            headers=openrouter_headers(),
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            timeout=60
        )

        if response.status_code != 200:
            print(
                "FILE QUESTION AI ERROR:",
                response.status_code,
                response.text
            )

            set_status(
                "ERROR",
                "AJ could not answer the file question."
            )

            return jsonify({
                "assistant": "AJ",
                "response": "AJ could not answer from the file right now.",
                "state": "ERROR"
            }), 500

        result_data = response.json()

        answer = (
            result_data
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )

        if not answer:
            answer = "AJ did not receive a valid answer."

        set_status(
            "ONLINE",
            "AJ is ready."
        )

        return jsonify({
            "assistant": "AJ",
            "response": answer.strip(),
            "filename": file_name,
            "state": "ONLINE"
        })

    except Exception as error:
        print("FILE QUESTION ERROR:", error)

        set_status(
            "ERROR",
            "AJ could not answer the file question."
        )

        return jsonify({
            "assistant": "AJ",
            "response": "AJ could not answer that file question.",
            "state": "ERROR"
        }), 500



# =========================================================
# TASK CONTROL API
# =========================================================

def _task_request_id(data):
    if not isinstance(data, dict):
        return ""
    return str(
        data.get("task_id", "")
    ).strip()


@app.route("/api/tasks", methods=["GET"])
def tasks():
    """Return all persisted AJ tasks."""
    try:
        return jsonify({
            "assistant": "AJ",
            "tasks": [
                task_to_dict(task)
                for task in get_all_tasks()
            ],
            "state": "ONLINE"
        })
    except Exception as error:
        print("TASK LIST ERROR:", error)
        return security_error(
            "AJ could not load the task list.",
            500
        )


@app.route("/api/tasks/current", methods=["GET"])
def current_task():
    """Return the current active task."""
    try:
        tasks_list = get_all_tasks()

        active = [
            task for task in tasks_list
            if task.get("status") in {
                "pending",
                "running",
                "waiting_confirmation"
            }
        ]

        task = active[-1] if active else None

        return jsonify({
            "assistant": "AJ",
            "task": task_to_dict(task),
            "summary": task_summary(task),
            "state": "ONLINE"
        })

    except Exception as error:
        print("CURRENT TASK ERROR:", error)
        return security_error(
            "AJ could not load the current task.",
            500
        )


@app.route("/api/tasks/start", methods=["POST"])
def start_task_api():
    """Start a persisted task."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return security_error(
            "Invalid task request.",
            400
        )

    task_id = _task_request_id(data)

    if not task_id:
        return security_error(
            "A task_id is required.",
            400
        )

    try:
        task = get_task(task_id)

        if not task:
            return security_error(
                "Task not found.",
                404
            )

        start_task(task)
        save_task(task)

        return jsonify({
            "assistant": "AJ",
            "task": task_to_dict(task),
            "summary": task_summary(task),
            "state": "ONLINE"
        })

    except Exception as error:
        print("TASK START ERROR:", error)
        return security_error(
            "AJ could not start that task.",
            500
        )


@app.route("/api/tasks/continue", methods=["POST"])
def continue_task_api():
    """
    Move a task to its next safe step.

    This endpoint changes task state only. It does not perform
    arbitrary shell commands or sensitive external actions.
    """
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return security_error(
            "Invalid task request.",
            400
        )

    task_id = _task_request_id(data)

    if not task_id:
        return security_error(
            "A task_id is required.",
            400
        )

    try:
        task = get_task(task_id)

        if not task:
            return security_error(
                "Task not found.",
                404
            )

        step = start_next_step(task)
        save_task(task)

        return jsonify({
            "assistant": "AJ",
            "task": task_to_dict(task),
            "step": step,
            "summary": task_summary(task),
            "state": "ONLINE"
        })

    except Exception as error:
        print("TASK CONTINUE ERROR:", error)
        return security_error(
            "AJ could not continue that task.",
            500
        )


@app.route("/api/tasks/confirm", methods=["POST"])
def confirm_task_api():
    """Explicitly approve the current sensitive task step."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return security_error(
            "Invalid task request.",
            400
        )

    task_id = _task_request_id(data)

    if not task_id:
        return security_error(
            "A task_id is required.",
            400
        )

    try:
        task = get_task(task_id)

        if not task:
            return security_error(
                "Task not found.",
                404
            )

        step = confirm_current_step(task)
        save_task(task)

        return jsonify({
            "assistant": "AJ",
            "task": task_to_dict(task),
            "step": step,
            "summary": task_summary(task),
            "state": "ONLINE"
        })

    except Exception as error:
        print("TASK CONFIRM ERROR:", error)
        return security_error(
            "AJ could not confirm that task step.",
            500
        )


@app.route("/api/tasks/cancel", methods=["POST"])
def cancel_task_api():
    """Cancel a persisted task."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return security_error(
            "Invalid task request.",
            400
        )

    task_id = _task_request_id(data)

    if not task_id:
        return security_error(
            "A task_id is required.",
            400
        )

    try:
        task = get_task(task_id)

        if not task:
            return security_error(
                "Task not found.",
                404
            )

        cancelled = cancel_task(task)
        save_task(task)

        if not cancelled:
            return security_error(
                "That task cannot be cancelled.",
                400
            )

        return jsonify({
            "assistant": "AJ",
            "task": task_to_dict(task),
            "summary": task_summary(task),
            "state": "ONLINE"
        })

    except Exception as error:
        print("TASK CANCEL ERROR:", error)
        return security_error(
            "AJ could not cancel that task.",
            500
        )



# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "AJ is running",
        "assistant": "AJ",
        "ai_provider": "OpenRouter",
        "command_center": True,
        "memory": True,
        "web_search": True,
        "file_intelligence": True,
        "voice_control": True,
        "voice_api": True,
        "task_engine": True,
        "task_api": True,
        "security": True,
        "file_upload_limit_mb": 5
    })


# =========================================================
# 413 FILE TOO LARGE
# =========================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "assistant": "AJ",
        "response": "The uploaded file or request is too large.",
        "state": "ERROR"
    }), 413


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":
    print("================================")
    print("        AJ AI ASSISTANT")
    print("================================")
    print("AJ is online.")
    print("AI Provider: OpenRouter")
    print("Command Center: ON")
    print("Memory: ON")
    print("Web Search: ON")
    print("File Intelligence: ON")
    print("Voice Control: ON")
    print("Security: ON")
    print("================================")

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
