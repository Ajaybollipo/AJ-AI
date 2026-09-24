from flask import Flask, jsonify, request, send_file, send_from_directory
from datetime import datetime
import os

from aj_brain import ask_aj


# ============================================================
# FLASK APP
# ============================================================

app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)


# ============================================================
# AJ STATUS
# ============================================================

AJ_STATUS = {
    "state": "ONLINE",
    "message": "AJ is ready.",
    "updated": datetime.now().strftime("%H:%M:%S")
}


def set_status(
    state,
    message
):

    AJ_STATUS["state"] = state

    AJ_STATUS["message"] = message

    AJ_STATUS["updated"] = (
        datetime.now().strftime("%H:%M:%S")
    )


# ============================================================
# HOME
# ============================================================

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


# ============================================================
# SIGNATURE / STATIC FILES
# ============================================================

@app.route(
    "/static/images/<path:filename>"
)
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


# ============================================================
# STATUS
# ============================================================

@app.route("/api/status")
def status():

    return jsonify({

        "assistant":
            "AJ",

        "state":
            AJ_STATUS["state"],

        "message":
            AJ_STATUS["message"],

        "time":
            AJ_STATUS["updated"]

    })


# ============================================================
# COMMAND
# ============================================================

@app.route(
    "/api/command",
    methods=["POST"]
)
def command():

    data = request.get_json(
        silent=True
    ) or {}


    message = data.get(
        "message",
        ""
    ).strip()


    history = data.get(
        "history",
        []
    )


    if not message:

        return jsonify({

            "assistant":
                "AJ",

            "response":
                "Please say something.",

            "state":
                "ONLINE"

        }), 400


    try:

        # ====================================================
        # THINKING
        # ====================================================

        set_status(
            "THINKING",
            "Understanding your request..."
        )


        # ====================================================
        # SEARCH DETECTION
        # ====================================================

        lower = message.lower()


        if any(
            word in lower
            for word in [
                "search",
                "look up",
                "find information",
                "find info"
            ]
        ):

            set_status(
                "SEARCHING",
                "Searching the web..."
            )


        # ====================================================
        # ACTION DETECTION
        # ====================================================

        if any(
            word in lower
            for word in [
                "open",
                "launch",
                "start",
                "go to",
                "take me"
            ]
        ):

            set_status(
                "EXECUTING",
                "Executing command..."
            )


        # ====================================================
        # AI
        # ====================================================

        response = ask_aj(
            message,
            history
        )


        # ====================================================
        # READY
        # ====================================================

        set_status(
            "ONLINE",
            "AJ is ready."
        )


        return jsonify({

            "assistant":
                "AJ",

            "response":
                response,

            "state":
                "ONLINE"

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

            "assistant":
                "AJ",

            "response":
                "I'm having trouble processing "
                "that right now.",

            "state":
                "ERROR"

        }), 500


# ============================================================
# RUN SERVER
# ============================================================

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
        "Static files: ON"
    )

    print(
        "Signature: ON"
    )

    print(
        "Server: http://0.0.0.0:5000"
    )

    print(
        "================================"
    )


    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )