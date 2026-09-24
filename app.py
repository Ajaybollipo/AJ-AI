from flask import Flask, jsonify, request, send_file, send_from_directory
from datetime import datetime
import os

from aj_brain import ask_aj


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
