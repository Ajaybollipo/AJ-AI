from flask import Flask, jsonify, request, send_file, send_from_directory
from datetime import datetime
import os
import tempfile
import time
from collections import defaultdict, deque
from werkzeug.utils import secure_filename
import requests

from aj_brain import ask_aj
from aj_files import prepare_file_for_ai
from aj_voice import process_voice_command


app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)

# =========================================================
# SECURITY CONFIG
# =========================================================

# Limit incoming HTTP bodies to protect the Render instance.
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

ALLOWED_FILE_EXTENSIONS = {
    "txt", "md", "py", "js", "html", "css", "json",
    "csv", "xml", "java", "c", "cpp", "sql", "pdf"
}

MAX_MESSAGE_LENGTH = 6000
MAX_HISTORY_ITEMS = 20
MAX_HISTORY_ITEM_LENGTH = 12000
MAX_FILE_CONTENT_LENGTH = 50000

# Lightweight in-memory rate limiter.
# This protects the public API without adding another database.
RATE_LIMITS = {
    "command": (30, 60),
    "voice": (30, 60),
    "upload": (10, 60),
    "file_question": (20, 60),
}

_request_log = defaultdict(deque)


def get_client_ip():
    # Do not trust arbitrary X-Forwarded-For values from clients.
    return request.remote_addr or "unknown"


def rate_limited(bucket):
    limit, window = RATE_LIMITS[bucket]
    now = time.monotonic()
    key = f"{bucket}:{get_client_ip()}"
    events = _request_log[key]

    while events and now - events[0] > window:
        events.popleft()

    if len(events) >= limit:
        return True

    events.append(now)
    return False


def allowed_file(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_FILE_EXTENSIONS


def security_error(message="Too many requests. Please try again shortly."):
    return jsonify({
        "assistant": "AJ",
        "response": message,
        "state": "ERROR"
    }), 429


def clean_history(history):
    if not isinstance(history, list):
        return []

    cleaned = []

    for item in history[-MAX_HISTORY_ITEMS:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in {"user", "assistant"}:
            continue

        if not isinstance(content, str):
            continue

        content = content.strip()

        if not content:
            continue

        cleaned.append({
            "role": role,
            "content": content[:MAX_HISTORY_ITEM_LENGTH]
        })

    return cleaned


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
            os.path.dirname(
                os.path.abspath(__file__)
            ),
            "index.html"
        )
    )


# =========================================================
# SIGNATURE / STATIC IMAGES
# =========================================================

@app.route("/static/images/<path:filename>")
def signature(filename):

    static_directory = os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
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

@app.route(
    "/api/voice",
    methods=["POST"]
)
def voice_command():

    if rate_limited("voice"):
        return security_error()

    data = request.get_json(
        silent=True
    ) or {}

    message = str(
        data.get(
            "message",
            ""
        )
    ).strip()

    if not message:
        return jsonify({
            "assistant": "AJ",
            "response": "I didn't hear a command.",
            "state": "ONLINE"
        }), 400


    try:

        result = process_voice_command(
            message
        )

        command = result.get(
            "command",
            message
        )

        if not command:

            return jsonify({
                "assistant": "AJ",
                "response": "Yes, Ajay?",
                "wake_word": result.get(
                    "wake_word",
                    False
                ),
                "state": "LISTENING"
            })


        set_status(
            "THINKING",
            "Processing voice command..."
        )


        response = ask_aj(
            command,
            []
        )


        set_status(
            "ONLINE",
            "AJ is ready."
        )


        return jsonify({
            "assistant": "AJ",
            "response": response,
            "command": command,
            "wake_word": result.get(
                "wake_word",
                False
            ),
            "state": "ONLINE"
        })


    except Exception as error:

        print(
            "VOICE COMMAND ERROR:",
            error
        )


        set_status(
            "ERROR",
            "AJ voice command failed."
        )


        return jsonify({
            "assistant": "AJ",
            "response": (
                "I couldn't process "
                "that voice command."
            ),
            "state": "ERROR"
        }), 500


# =========================================================
# COMMAND API
# =========================================================

@app.route(
    "/api/command",
    methods=["POST"]
)
def command():

    if rate_limited("command"):
        return security_error()

    data = request.get_json(
        silent=True
    ) or {}

    message = str(
        data.get(
            "message",
            ""
        )
    ).strip()

    history = clean_history(data.get("history", []))

    if not message:

        return jsonify({
            "assistant": "AJ",
            "response": "Please say something.",
            "state": "ONLINE"
        }), 400


    if len(message) > 6000:

        return jsonify({
            "assistant": "AJ",
            "response": (
                "Your message is too long. "
                "Please shorten it."
            ),
            "state": "ERROR"
        }), 400


    try:

        lower = message.lower()


        set_status(
            "THINKING",
            "Understanding your request..."
        )


        if any(
            word in lower
            for word in [
                "search",
                "look up",
                "find information",
                "find info",
                "google",
                "latest",
                "current",
                "news"
            ]
        ):

            set_status(
                "SEARCHING",
                "Searching..."
            )


        elif any(
            word in lower
            for word in [
                "open",
                "launch",
                "start",
                "play",
                "go to",
                "take me",
                "calculate",
                "weather"
            ]
        ):

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

        print(
            "COMMAND ERROR:",
            error
        )


        set_status(
            "ERROR",
            "AJ encountered an error."
        )


        return jsonify({
            "assistant": "AJ",
            "response": (
                "I'm having trouble "
                "processing that right now."
            ),
            "state": "ERROR"
        }), 500


# =========================================================
# FILE INTELLIGENCE
# =========================================================

@app.route(
    "/api/upload",
    methods=["POST"]
)
def upload_file():

    if rate_limited("upload"):
        return security_error()

    if "file" not in request.files:

        return jsonify({
            "assistant": "AJ",
            "response": "No file was uploaded.",
            "state": "ERROR"
        }), 400


    uploaded_file = request.files["file"]


    original_filename = uploaded_file.filename or ""
    safe_filename = secure_filename(original_filename)

    if not safe_filename:
        return jsonify({
            "assistant": "AJ",
            "response": "Please select a file.",
            "state": "ERROR"
        }), 400


    if not allowed_file(safe_filename):
        return jsonify({
            "assistant": "AJ",
            "response": (
                "That file type is not allowed. "
                "Please upload a supported document or code file."
            ),
            "state": "ERROR"
        }), 400

    # Check the uploaded stream size before saving it.
    uploaded_file.stream.seek(0, os.SEEK_END)
    upload_size = uploaded_file.stream.tell()
    uploaded_file.stream.seek(0)

    if upload_size > 5 * 1024 * 1024:
        return jsonify({
            "assistant": "AJ",
            "response": "File is too large. Maximum file size is 5 MB.",
            "state": "ERROR"
        }), 413

    try:

        set_status(
            "READING",
            "Reading your file..."
        )

        suffix = os.path.splitext(
            safe_filename
        )[1].lower()


        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temporary_file:

            uploaded_file.save(
                temporary_file.name
            )

            temporary_path = temporary_file.name


        result = prepare_file_for_ai(
            temporary_path
        )


        try:

            os.remove(
                temporary_path
            )

        except Exception:

            pass


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

        content = result.get(
            "content",
            ""
        )

        truncated = result.get(
            "truncated",
            False
        )


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
                "\n\nNote: The file was large, "
                "so AJ analyzed the first "
                "50,000 characters."
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

        print(
            "FILE UPLOAD ERROR:",
            error
        )


        set_status(
            "ERROR",
            "AJ could not read the file."
        )


        return jsonify({
            "assistant": "AJ",
            "response": (
                "AJ could not process "
                "that file."
            ),
            "state": "ERROR"
        }), 500


# =========================================================
# FILE QUESTION API
# =========================================================

@app.route(
    "/api/file-question",
    methods=["POST"]
)
def file_question():

    if rate_limited("file_question"):
        return security_error()

    data = request.get_json(
        silent=True
    ) or {}

    question = str(
        data.get("question", "")
    ).strip()

    content = str(
        data.get("content", "")
    )

    file_name = str(
        data.get("filename", "uploaded file")
    )

    if len(question) > MAX_MESSAGE_LENGTH:
        return jsonify({
            "assistant": "AJ",
            "response": "Your file question is too long.",
            "state": "ERROR"
        }), 400

    if not question:
        return jsonify({
            "assistant": "AJ",
            "response": "Please ask a question about the file.",
            "state": "ERROR"
        }), 400

    if not content:
        return jsonify({
            "assistant": "AJ",
            "response": "No file content was provided.",
            "state": "ERROR"
        }), 400

    if len(content) > MAX_FILE_CONTENT_LENGTH:
        content = content[:MAX_FILE_CONTENT_LENGTH]

    if len(file_name) > 255:
        file_name = file_name[:255]

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
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Ajaybollipo/AJ-AI",
                "X-Title": "AJ Personal AI Assistant"
            },
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
            return jsonify({
                "assistant": "AJ",
                "response": "AJ could not answer from the file right now.",
                "state": "ERROR"
            }), 500

        data = response.json()

        answer = (
            data
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

        print(
            "FILE QUESTION ERROR:",
            error
        )

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
        "security": True,
        "file_upload_limit_mb": 5
    })


# =========================================================
# REQUEST SIZE ERROR
# =========================================================

@app.errorhandler(413)
def request_too_large(error):
    return jsonify({
        "assistant": "AJ",
        "response": "Request is too large. Please reduce the size and try again.",
        "state": "ERROR"
    }), 413


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "        AJ AI ASSISTANT"
    )

    print(
        "================================"
    )

    print(
        "AJ is online."
    )

    print(
        "AI Provider: OpenRouter"
    )

    print(
        "Command Center: ON"
    )

    print(
        "Memory: ON"
    )

    print(
        "Web Search: ON"
    )

    print(
        "File Intelligence: ON"
    )

    print(
        "Voice Control: ON"
    )

    print(
        "================================"
    )


    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )


    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
