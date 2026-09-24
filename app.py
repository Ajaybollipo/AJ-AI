from flask import Flask, jsonify, request, send_file, send_from_directory
from datetime import datetime
import os
import tempfile

from aj_brain import ask_aj
from aj_files import prepare_file_for_ai


app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)


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
# COMMAND API
# =========================================================

@app.route(
    "/api/command",
    methods=["POST"]
)
def command():

    data = request.get_json(
        silent=True
    ) or {}

    message = str(
        data.get(
            "message",
            ""
        )
    ).strip()

    history = data.get(
        "history",
        []
    )


    # =====================================================
    # EMPTY MESSAGE
    # =====================================================

    if not message:

        return jsonify({
            "assistant": "AJ",
            "response": "Please say something.",
            "state": "ONLINE"
        }), 400


    # =====================================================
    # MESSAGE LIMIT
    # =====================================================

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


        # =================================================
        # THINKING
        # =================================================

        set_status(
            "THINKING",
            "Understanding your request..."
        )


        # =================================================
        # SEARCHING
        # =================================================

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


        # =================================================
        # EXECUTING
        # =================================================

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


        # =================================================
        # AI BRAIN
        # =================================================

        response = ask_aj(
            message,
            history
        )


        # =================================================
        # BACK ONLINE
        # =================================================

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

    if "file" not in request.files:

        return jsonify({
            "assistant": "AJ",
            "response": "No file was uploaded.",
            "state": "ERROR"
        }), 400


    uploaded_file = request.files["file"]


    if not uploaded_file.filename:

        return jsonify({
            "assistant": "AJ",
            "response": "Please select a file.",
            "state": "ERROR"
        }), 400


    try:

        set_status(
            "READING",
            "Reading your file..."
        )


        # =================================================
        # TEMPORARY FILE
        # =================================================

        suffix = os.path.splitext(
            uploaded_file.filename
        )[1]


        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temporary_file:

            uploaded_file.save(
                temporary_file.name
            )

            temporary_path = temporary_file.name


        # =================================================
        # READ FILE
        # =================================================

        result = prepare_file_for_ai(
            temporary_path
        )


        # =================================================
        # REMOVE TEMP FILE
        # =================================================

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


        # =================================================
        # FILE CONTENT
        # =================================================

        file_name = result.get(
            "name",
            uploaded_file.filename
        )

        content = result.get(
            "content",
            ""
        )


        truncated = result.get(
            "truncated",
            False
        )


        # =================================================
        # ASK AJ TO ANALYZE FILE
        # =================================================

        analysis_prompt = f"""
You are AJ, a personal AI assistant.

The user uploaded this file:

FILE NAME:
{file_name}

FILE CONTENT:
{content}

Analyze the uploaded file carefully.

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
        "voice": True
    })


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
