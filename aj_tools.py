import ast
import operator
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus

import requests


# ============================================================
# AJ ACTION ENGINE
# ============================================================

WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "instagram": "https://www.instagram.com",
    "chatgpt": "https://chatgpt.com",
    "gmail": "https://mail.google.com",
    "whatsapp": "https://web.whatsapp.com",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
    "spotify": "https://open.spotify.com",
    "ajai": "https://ajai-in.up.railway.app/"
}


# ============================================================
# INDIA TIME
# ============================================================

INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def get_time():
    return datetime.now(INDIA_TIMEZONE).strftime("%I:%M %p")


def get_date():
    return datetime.now(INDIA_TIMEZONE).strftime("%d %B %Y")


# ============================================================
# COMMAND CLEANING
# ============================================================

def clean_command(message):
    text = message.strip()

    prefixes = [
        "hey aj,",
        "hey aj:",
        "hey aj ",
        "okay aj,",
        "okay aj:",
        "okay aj ",
        "ok aj,",
        "ok aj:",
        "ok aj ",
        "aj,",
        "aj:",
        "aj "
    ]

    lower = text.lower()

    for prefix in prefixes:
        if lower.startswith(prefix):
            text = text[len(prefix):].strip()
            break

    return text


# ============================================================
# WEBSITE DETECTION
# ============================================================

def find_website(target):
    target = target.lower().strip()
    target = target.replace(",", " ")
    target = target.replace(".", " ")

    aliases = {
        "yt": "youtube",
        "youtube videos": "youtube",
        "google search": "google",
        "git hub": "github",
        "ig": "instagram",
        "open ai": "chatgpt",
        "chat gpt": "chatgpt",
        "google mail": "gmail",
        "email": "gmail",
        "mail": "gmail",
        "whats app": "whatsapp",
        "linked in": "linkedin",
        "music": "spotify",
        "yt": "youtube",
        "yt videos": "youtube",
        "git hub": "github",
        "open ai": "chatgpt",
        "chat gpt": "chatgpt",
        "google mail": "gmail",
        "whats app": "whatsapp",
        "linked in": "linkedin"
    }

    for alias, site in aliases.items():
        if alias in target:
            return site

    remove_words = [
        "website",
        "app",
        "application",
        "page",
        "site",
        "my"
    ]

    for word in remove_words:
        target = target.replace(word, " ")

    target = " ".join(target.split())

    if target in WEBSITES:
        return target

    for site in WEBSITES:
        if site in target:
            return site

    return None


def open_website(name):
    name = name.lower().strip()

    if name not in WEBSITES:
        return {
            "success": False,
            "action": "open_website",
            "message": f"I don't know how to open {name} yet."
        }

    url = WEBSITES[name]

    return {
        "success": True,
        "action": "open_website",
        "name": name,
        "url": url,
        "message": f"Opening {name.title()}."
    }


# ============================================================
# GOOGLE SEARCH
# ============================================================

def search_web(query):
    query = query.strip()

    if not query:
        return {
            "success": False,
            "action": "search",
            "message": "What should I search for?"
        }

    encoded = quote_plus(query)

    url = (
        "https://www.google.com/search?q="
        + encoded
    )

    return {
        "success": True,
        "action": "search",
        "query": query,
        "url": url,
        "browser_url": url,
        "message": f"Searching Google for {query}."
    }


# ============================================================
# YOUTUBE SEARCH
# ============================================================

def youtube_search(query):
    query = query.strip()

    if not query:
        return {
            "success": False,
            "action": "youtube_search",
            "message": "What should I search for on YouTube?"
        }

    encoded = quote_plus(query)

    url = (
        "https://www.youtube.com/results?search_query="
        + encoded
    )

    return {
        "success": True,
        "action": "youtube_search",
        "query": query,
        "url": url,
        "browser_url": url,
        "message": f"Searching YouTube for {query}."
    }


# ============================================================
# SMART CALCULATOR
# ============================================================

MATH_OPERATORS = {
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


def _safe_math_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("Invalid number")

    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in MATH_OPERATORS:
            raise ValueError("Unsupported operator")
        return MATH_OPERATORS[type(node.op)](
            _safe_math_node(node.operand)
        )

    if isinstance(node, ast.BinOp):
        if type(node.op) not in MATH_OPERATORS:
            raise ValueError("Unsupported operator")

        left = _safe_math_node(node.left)
        right = _safe_math_node(node.right)

        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Power too large")

        return MATH_OPERATORS[type(node.op)](left, right)

    raise ValueError("Unsupported expression")


def _safe_math(expression):
    tree = ast.parse(expression, mode="eval")
    return _safe_math_node(tree.body)


def calculate_expression(expression):
    expression = expression.strip()

    if not expression:
        return {
            "success": False,
            "action": "calculate",
            "message": "What should I calculate?"
        }

    try:
        expression = expression.replace("×", "*")
        expression = expression.replace("÷", "/")
        expression = expression.replace("^", "**")

        if expression.endswith("%"):
            expression = expression[:-1].strip()
            result = float(expression) / 100
        else:
            result = _safe_math(expression)

        if isinstance(result, float):

            if result.is_integer():
                result = int(result)

            else:
                result = round(result, 10)

        return {
            "success": True,
            "action": "calculate",
            "expression": expression,
            "result": result,
            "message": f"The answer is {result}."
        }

    except Exception:
        return {
            "success": False,
            "action": "calculate",
            "message": "I couldn't calculate that expression."
        }


def looks_like_calculation(text):
    math_symbols = [
        "+",
        "-",
        "*",
        "/",
        "%",
        "×",
        "÷",
        "^"
    ]

    return any(
        symbol in text
        for symbol in math_symbols
    )


# ============================================================
# WEATHER
# ============================================================

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}


# ============================================================
# COMMON INDIAN CITIES
# ============================================================

CITY_COORDINATES = {
    "eluru": {
        "name": "Eluru",
        "latitude": 16.7107,
        "longitude": 81.0952
    },
    "hyderabad": {
        "name": "Hyderabad",
        "latitude": 17.3850,
        "longitude": 78.4867
    },
    "vijayawada": {
        "name": "Vijayawada",
        "latitude": 16.5062,
        "longitude": 80.6480
    },
    "visakhapatnam": {
        "name": "Visakhapatnam",
        "latitude": 17.6868,
        "longitude": 83.2185
    },
    "vizag": {
        "name": "Visakhapatnam",
        "latitude": 17.6868,
        "longitude": 83.2185
    },
    "rajahmundry": {
        "name": "Rajahmundry",
        "latitude": 17.0005,
        "longitude": 81.8040
    },
    "kakinada": {
        "name": "Kakinada",
        "latitude": 16.9891,
        "longitude": 82.2475
    },
    "amaravati": {
        "name": "Amaravati",
        "latitude": 16.5740,
        "longitude": 80.3575
    },
    "guntur": {
        "name": "Guntur",
        "latitude": 16.3067,
        "longitude": 80.4365
    },
    "tirupati": {
        "name": "Tirupati",
        "latitude": 13.6288,
        "longitude": 79.4192
    },
    "chennai": {
        "name": "Chennai",
        "latitude": 13.0827,
        "longitude": 80.2707
    },
    "bangalore": {
        "name": "Bengaluru",
        "latitude": 12.9716,
        "longitude": 77.5946
    },
    "bengaluru": {
        "name": "Bengaluru",
        "latitude": 12.9716,
        "longitude": 77.5946
    },
    "mumbai": {
        "name": "Mumbai",
        "latitude": 19.0760,
        "longitude": 72.8777
    },
    "delhi": {
        "name": "Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090
    },
    "kolkata": {
        "name": "Kolkata",
        "latitude": 22.5726,
        "longitude": 88.3639
    },
    "pune": {
        "name": "Pune",
        "latitude": 18.5204,
        "longitude": 73.8567
    },
    "goa": {
        "name": "Goa",
        "latitude": 15.2993,
        "longitude": 74.1240
    },
    "new delhi": {
        "name": "New Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090
    }
}


def get_weather_code_description(code):
    return WEATHER_CODES.get(
        code,
        "Unknown weather conditions"
    )


# ============================================================
# LOCATION LOOKUP
# ============================================================

def geocode_location(location):
    location = location.strip()

    if not location:
        location = "Eluru"

    normalized = " ".join(
        location.lower().split()
    )

    # First use built-in coordinates
    if normalized in CITY_COORDINATES:

        city = CITY_COORDINATES[normalized]

        return {
            "name": city["name"],
            "latitude": city["latitude"],
            "longitude": city["longitude"]
        }

    # Otherwise use Open-Meteo geocoding
    url = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )

    params = {
        "name": location,
        "count": 5,
        "language": "en",
        "format": "json"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        results = data.get(
            "results",
            []
        )

        if not results:
            return None

        # Prefer India if multiple results exist
        for result in results:

            if result.get("country_code") == "IN":

                return {
                    "name": result.get(
                        "name",
                        location
                    ),
                    "latitude": result.get(
                        "latitude"
                    ),
                    "longitude": result.get(
                        "longitude"
                    )
                }

        result = results[0]

        return {
            "name": result.get(
                "name",
                location
            ),
            "latitude": result.get(
                "latitude"
            ),
            "longitude": result.get(
                "longitude"
            )
        }

    except Exception as error:

        print(
            "GEOCODING ERROR:",
            error
        )

        return None


# ============================================================
# GET LIVE WEATHER
# ============================================================

def get_weather(location="Eluru"):

    place = geocode_location(
        location
    )

    if not place:

        return {
            "success": False,
            "action": "weather",
            "message":
                f"I couldn't find weather information for {location}."
        }

    url = (
        "https://api.open-meteo.com/v1/forecast"
    )

    params = {
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "weather_code,"
            "wind_speed_10m"
        ),
        "timezone": "auto"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        current = data.get(
            "current",
            {}
        )

        temperature = current.get(
            "temperature_2m"
        )

        humidity = current.get(
            "relative_humidity_2m"
        )

        feels_like = current.get(
            "apparent_temperature"
        )

        weather_code = current.get(
            "weather_code"
        )

        wind_speed = current.get(
            "wind_speed_10m"
        )

        description = (
            get_weather_code_description(
                weather_code
            )
        )

        place_name = place["name"]

        message = (
            f"Current weather in "
            f"{place_name}: "
            f"{temperature}°C, "
            f"{description}. "
            f"It feels like "
            f"{feels_like}°C. "
            f"Humidity is "
            f"{humidity}%. "
            f"Wind speed is "
            f"{wind_speed} km/h."
        )

        return {
            "success": True,
            "action": "weather",
            "location": place_name,
            "temperature": temperature,
            "humidity": humidity,
            "feels_like": feels_like,
            "wind_speed": wind_speed,
            "description": description,
            "message": message
        }

    except Exception as error:

        print(
            "WEATHER ERROR:",
            error
        )

        return {
            "success": False,
            "action": "weather",
            "message":
                "I couldn't connect to the "
                "weather service right now."
        }


# ============================================================
# WEATHER COMMAND DETECTION
# ============================================================

def extract_weather_location(text):

    lower = text.lower().strip()

    prefixes = [
        "what's the weather in ",
        "what is the weather in ",
        "weather in ",
        "weather at ",
        "weather for ",
        "temperature in ",
        "temperature at ",
        "temperature for ",
        "what's the temperature in ",
        "what is the temperature in "
    ]

    for prefix in prefixes:

        if lower.startswith(prefix):

            location = text[
                len(prefix):
            ].strip()

            if location:
                return location

    return None


def is_general_weather_command(text):

    lower = text.lower().strip()

    commands = [
        "weather",
        "what's the weather",
        "what is the weather",
        "weather now",
        "current weather",
        "check weather",
        "check the weather",
        "how is the weather",
        "how's the weather",
        "temperature",
        "what's the temperature",
        "what is the temperature",
        "temperature now"
    ]

    return lower in commands


# ============================================================
# INTENT DETECTION
# ============================================================

def detect_intent(message):

    text = clean_command(message)

    lower = text.lower().strip()

    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    time_phrases = [
        "what time is it",
        "what's the time",
        "tell me the time",
        "current time",
        "time now",
        "what is the time",
        "time please"
    ]

    if any(
        phrase in lower
        for phrase in time_phrases
    ):

        return {
            "intent": "time",
            "argument": ""
        }

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    date_phrases = [
        "what is today's date",
        "what's today's date",
        "tell me today's date",
        "today's date",
        "what date is it",
        "current date",
        "date today",
        "what is the date",
        "today date"
    ]

    if any(
        phrase in lower
        for phrase in date_phrases
    ):

        return {
            "intent": "date",
            "argument": ""
        }

    # --------------------------------------------------------
    # WEATHER
    # --------------------------------------------------------

    weather_location = extract_weather_location(
        text
    )

    if weather_location:

        return {
            "intent": "weather",
            "argument": weather_location
        }

    if is_general_weather_command(text):

        return {
            "intent": "weather",
            "argument": "Eluru"
        }

    # --------------------------------------------------------
    # CALCULATOR
    # --------------------------------------------------------

    calculation_prefixes = [
        "calculate ",
        "compute ",
        "solve "
    ]

    for prefix in calculation_prefixes:

        if lower.startswith(prefix):

            expression = text[
                len(prefix):
            ].strip()

            return {
                "intent": "calculate",
                "argument": expression
            }

    if lower.startswith("what is "):

        expression = text[8:].strip()

        if looks_like_calculation(
            expression
        ):

            return {
                "intent": "calculate",
                "argument": expression
            }

    if lower.startswith("what's "):

        expression = text[7:].strip()

        if looks_like_calculation(
            expression
        ):

            return {
                "intent": "calculate",
                "argument": expression
            }

    # --------------------------------------------------------
    # YOUTUBE SEARCH
    # --------------------------------------------------------

    youtube_prefixes = [
        "search youtube for ",
        "search youtube ",
        "youtube search ",
        "find on youtube ",
        "look up on youtube "
    ]

    for prefix in youtube_prefixes:

        if lower.startswith(prefix):

            query = text[
                len(prefix):
            ].strip()

            return {
                "intent": "youtube_search",
                "argument": query
            }

    # --------------------------------------------------------
    # GOOGLE SEARCH
    # --------------------------------------------------------

    search_prefixes = [
        "search for ",
        "search ",
        "look up ",
        "find information about ",
        "find info about ",
        "google "
    ]

    for prefix in search_prefixes:

        if lower.startswith(prefix):

            query = text[
                len(prefix):
            ].strip()

            if query:

                return {
                    "intent": "search",
                    "argument": query
                }

    # --------------------------------------------------------
    # WEBSITE OPENING
    # --------------------------------------------------------

    action_phrases = [
        "open",
        "launch",
        "start",
        "go to",
        "take me to",
        "bring me to",
        "visit",
        "show me",
        "i want to use",
        "i want to watch",
        "i want to open",
        "can you open",
        "please open",
        "please launch"
    ]

    for phrase in action_phrases:

        if lower.startswith(phrase):

            target = lower[
                len(phrase):
            ].strip()

            site = find_website(
                target
            )

            if site:

                return {
                    "intent": "open_website",
                    "argument": site
                }

    # --------------------------------------------------------
    # NATURAL WEBSITE COMMANDS
    # --------------------------------------------------------

    site = find_website(
        lower
    )

    natural_words = [
        "want",
        "need",
        "take",
        "bring",
        "open",
        "launch",
        "watch",
        "visit",
        "go"
    ]

    if (
        site
        and any(
            word in lower
            for word in natural_words
        )
    ):

        return {
            "intent": "open_website",
            "argument": site
        }

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return {
        "intent": "unknown",
        "argument": ""
    }


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(
    tool,
    argument=""
):

    if tool == "time":

        return {
            "success": True,
            "action": "time",
            "message":
                f"The current time is "
                f"{get_time()}."
        }

    if tool == "date":

        return {
            "success": True,
            "action": "date",
            "message":
                f"Today is "
                f"{get_date()}."
        }

    if tool == "weather":

        return get_weather(
            argument
        )

    if tool == "calculate":

        return calculate_expression(
            argument
        )

    if tool == "open_website":

        return open_website(
            argument
        )

    if tool == "search":

        return search_web(
            argument
        )

    if tool == "youtube_search":

        return youtube_search(
            argument
        )

    return {
        "success": False,
        "action": "unknown",
        "message":
            f"Tool '{tool}' is not available yet."
    }


# ============================================================
# RUN COMMAND
# ============================================================

def run_command(message):

    detected = detect_intent(
        message
    )

    intent = detected["intent"]

    argument = detected["argument"]

    if intent == "unknown":

        return {
            "handled": False,
            "result": None
        }

    result = execute_tool(
        intent,
        argument
    )

    return {
        "handled": True,
        "result": result
    }


# ============================================================
# TEST MODE
# ============================================================

if __name__ == "__main__":

    print()
    print("================================")
    print("       AJ ACTION ENGINE")
    print("================================")

    print(
        "India Time:",
        get_time()
    )

    print(
        "India Date:",
        get_date()
    )

    print()
    print("Calculator Test:")

    calculator_test = run_command(
        "calculate 125 × 48"
    )

    print(
        calculator_test["result"]["message"]
    )

    print()
    print("Hyderabad Weather Test:")

    weather_test = run_command(
        "weather in Hyderabad"
    )

    print(
        weather_test["result"]["message"]
    )

    print()
    print("================================")
