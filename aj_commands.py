import ast
import operator
import re
import requests
from datetime import datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from aj_memory import remember, recall, get_all_memory, clear_memory


OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


SITES = {
    "youtube": "https://www.youtube.com/",
    "google": "https://www.google.com/",
    "gmail": "https://mail.google.com/",
    "instagram": "https://www.instagram.com/",
    "facebook": "https://www.facebook.com/",
    "whatsapp": "https://web.whatsapp.com/",
    "github": "https://github.com/",
    "linkedin": "https://www.linkedin.com/",
    "spotify": "https://open.spotify.com/",
    "netflix": "https://www.netflix.com/",
    "chatgpt": "https://chatgpt.com/",
    "gemini": "https://gemini.google.com/",
    "amazon": "https://www.amazon.in/",
    "x": "https://x.com/",
    "twitter": "https://x.com/",
}


def _calc(node):

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value

    if isinstance(node, ast.BinOp):

        if type(node.op) not in OPS:
            raise ValueError("Unsupported operator")

        left = _calc(node.left)
        right = _calc(node.right)

        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Power too large")

        return OPS[type(node.op)](left, right)

    if isinstance(node, ast.UnaryOp):

        if type(node.op) not in OPS:
            raise ValueError("Unsupported operator")

        return OPS[type(node.op)](
            _calc(node.operand)
        )

    raise ValueError("Unsupported expression")


def calculator(text):

    expression = re.sub(
        r"^(calculate|calc|what is)\s+",
        "",
        text.strip(),
        flags=re.I
    )

    expression = (
        expression
        .replace("×", "*")
        .replace("÷", "/")
        .replace("^", "**")
    )

    if not re.fullmatch(
        r"[0-9+\-*/().%\s*]+",
        expression
    ):
        return None

    try:

        value = _calc(
            ast.parse(
                expression,
                mode="eval"
            ).body
        )

        if isinstance(value, float):
            return f"The answer is {value:g}."

        return f"The answer is {value}."

    except Exception:

        return "I couldn't calculate that."


def get_weather(city):

    coordinates = {

        "hyderabad": (
            17.3850,
            78.4867
        ),

        "visakhapatnam": (
            17.6868,
            83.2185
        ),

        "vijayawada": (
            16.5062,
            80.6480
        ),

        "delhi": (
            28.6139,
            77.2090
        ),

        "mumbai": (
            19.0760,
            72.8777
        ),

        "chennai": (
            13.0827,
            80.2707
        ),

        "bengaluru": (
            12.9716,
            77.5946
        ),

        "bangalore": (
            12.9716,
            77.5946
        ),
    }

    key = city.lower().strip()

    if key not in coordinates:
        return None

    latitude, longitude = coordinates[key]

    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "weather_code,"
                "wind_speed_10m"
            ),
        },
        timeout=8,
    )

    response.raise_for_status()

    current = response.json()["current"]

    return (
        f"Weather in {city.title()}: "
        f"{current['temperature_2m']}°C, "
        f"humidity {current['relative_humidity_2m']}%, "
        f"wind {current['wind_speed_10m']} km/h."
    )


def handle_command(message):

    raw = message.strip()
    lower = raw.lower()

    # ==========================================
    # OPEN WEBSITES
    # ==========================================

    match = re.match(
        r"^(?:open|launch|start|go to|take me to|visit)\s+(.+)$",
        lower
    )

    if match:

        site = match.group(1).strip()

        site = re.sub(
            r"\s+website$",
            "",
            site
        )

        if site in SITES:

            return (
                f"Opening {site.title()}: "
                f"{SITES[site]}"
            )

    # ==========================================
    # YOUTUBE
    # ==========================================

    match = re.match(
        r"^(?:play|search|find)\s+(.+?)"
        r"\s+(?:on\s+)?youtube$",
        raw,
        re.I
    )

    if match:

        query = match.group(1).strip()

        return (
            "Opening YouTube search: "
            "https://www.youtube.com/results?search_query="
            + quote_plus(query)
        )

    # ==========================================
    # GOOGLE SEARCH
    # ==========================================

    match = re.match(
        r"^(?:search|google)\s+(?:for\s+)?(.+)$",
        raw,
        re.I
    )

    if match:

        query = match.group(1).strip()

        return (
            "Searching Google: "
            "https://www.google.com/search?q="
            + quote_plus(query)
        )

    # ==========================================
    # TIME
    # ==========================================

    if lower in {
        "time",
        "what time is it",
        "current time"
    }:

        return datetime.now(
            ZoneInfo("Asia/Kolkata")
        ).strftime(
            "The current time is %I:%M %p."
        )

    # ==========================================
    # DATE
    # ==========================================

    if lower in {
        "date",
        "today",
        "today's date",
        "what is today's date"
    }:

        return datetime.now(
            ZoneInfo("Asia/Kolkata")
        ).strftime(
            "Today is %d %B %Y."
        )

    # ==========================================
    # CALCULATOR
    # ==========================================

    if lower.startswith(
        (
            "calculate ",
            "calc ",
            "what is "
        )
    ):

        result = calculator(raw)

        if result:
            return result

    # ==========================================
    # WEATHER
    # ==========================================

    match = re.match(
        r"^(?:weather|weather in)\s+(.+)$",
        raw,
        re.I
    )

    if match:

        city = match.group(1).strip()

        try:

            result = get_weather(city)

            if result:
                return result

        except Exception:

            return (
                "I couldn't get live weather "
                "right now."
            )

    # ==========================================
    # MEMORY
    # ==========================================

    match = re.match(
        r"^remember(?: that)?\s+(.+?)"
        r"\s*(?:is|=)\s*(.+)$",
        raw,
        re.I
    )

    if match:

        key = re.sub(
            r"[^a-z0-9_]+",
            "_",
            match.group(1)
            .strip()
            .lower()
        ).strip("_")

        value = match.group(2).strip()

        remember(
            key,
            value
        )

        return (
            f"I'll remember that "
            f"{match.group(1).strip()} "
            f"is {value}."
        )

    # ==========================================
    # SHOW MEMORY
    # ==========================================

    if lower in {
        "show memory",
        "my memories",
        "what do you remember about me"
    }:

        memory = get_all_memory()

        if not memory:
            return (
                "I don't have any saved "
                "memories yet."
            )

        return (
            "Here is what I remember:\n\n"
            + "\n".join(
                f"{key}: {value}"
                for key, value in memory.items()
            )
        )

    # ==========================================
    # CLEAR MEMORY
    # ==========================================

    if lower in {
        "clear memory",
        "forget everything",
        "delete my memory"
    }:

        clear_memory()

        return "Saved memory cleared."

    # ==========================================
    # STUDY MODE
    # ==========================================

    if lower.startswith(
        (
            "study mode",
            "study:"
        )
    ):

        content = raw.split(
            ":",
            1
        )[-1].strip()

        return (
            "__AJ_MODE_STUDY__"
            + content
        )

    # ==========================================
    # CODING MODE
    # ==========================================

    if lower.startswith(
        (
            "coding mode",
            "code:"
        )
    ):

        content = raw.split(
            ":",
            1
        )[-1].strip()

        return (
            "__AJ_MODE_CODING__"
            + content
        )

    return None
