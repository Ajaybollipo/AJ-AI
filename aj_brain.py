from datetime import datetime
import os
import requests
from aj_commands import handle_command
import webbrowser

from aj_memory import remember, get_all_memory, clear_memory


# =========================
# OPENROUTER CONFIG
# =========================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openrouter/free"

# OpenRouter fallback models.
# OpenRouter tries these in order if a model/provider is
# rate-limited or temporarily unavailable.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# =========================
# OPEN WEBSITES
# =========================

websites = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "instagram": "https://www.instagram.com",
    "chatgpt": "https://chatgpt.com",
    "gmail": "https://mail.google.com"
}


# =========================
# MEMORY
# =========================

def process_memory(message):
    text = message.strip()
    lower = text.lower()

    patterns = {
        "my favorite color is ": "favorite_color",
        "my favorite food is ": "favorite_food",
        "my favorite movie is ": "favorite_movie",
        "i study at ": "college"
    }

    for phrase, key in patterns.items():
        if phrase in lower:
            start = lower.index(phrase) + len(phrase)
            value = text[start:].strip()

            if value:
                remember(key, value)

    if lower.startswith("remember that "):
        value = text[len("remember that "):].strip()

        if value:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            remember(f"note_{timestamp}", value)
            return True

    return False


def build_memory_text():
    memory = get_all_memory()

    if not memory:
        return "No saved personal memory."

    return "\n".join(
        f"- {key}: {value}"
        for key, value in memory.items()
    )


# =========================
# FORGET MEMORY
# =========================

def forget_memory(message):
    lower = message.lower()

    memory = get_all_memory()

    memory_map = {
        "forget my favorite color": "favorite_color",
        "forget my favorite food": "favorite_food",
        "forget my favorite movie": "favorite_movie"
    }

    for command, key in memory_map.items():
        if command in lower:
            if key in memory:
                del memory[key]

                from aj_memory import save_memory
                save_memory(memory)

                return f"I forgot your {key.replace('_', ' ')}."

            return f"I don't have your {key.replace('_', ' ')} saved."

    return None


# =========================
# WEB SEARCH
# =========================

def web_search(query):

    try:
        from ddgs import DDGS

        results = []

        with DDGS() as ddgs:

            search_results = ddgs.text(
                query,
                region="wt-wt",
                safesearch="moderate",
                timelimit=None,
                max_results=8
            )

            for result in search_results:

                title = result.get("title", "").strip()
                url = result.get("href", "").strip()
                snippet = result.get("body", "").strip()

                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    })

        if not results:
            return f"I couldn't find useful results for '{query}'."

        # =========================
        # PREPARE SEARCH RESULTS
        # =========================

        search_text = ""

        for i, result in enumerate(results, 1):

            search_text += (
                f"RESULT {i}\n"
                f"TITLE: {result['title']}\n"
                f"URL: {result['url']}\n"
                f"DESCRIPTION: {result['snippet']}\n\n"
            )

        # =========================
        # NO OPENROUTER
        # =========================

        if not OPENROUTER_API_KEY:

            output = f"Search results for: {query}\n\n"

            for i, result in enumerate(results, 1):
                output += (
                    f"{i}. {result['title']}\n"
                    f"{result['snippet']}\n"
                    f"Source: {result['url']}\n\n"
                )

            return output.strip()

        # =========================
        # AI SEARCH SUMMARY
        # =========================

        prompt = f"""
You are AJ, a personal AI assistant.

The user asked:

{query}

Web search results:

{search_text}

Create the most useful answer possible using ONLY these
search results.

IMPORTANT:

- Answer the user's actual question.
- Do NOT simply list websites.
- Identify the actual headlines or important information.
- For news searches, summarize the actual news stories.
- Prefer recent-looking results when the user asks for latest,
  today, current, recent, or breaking information.
- Do not invent dates, facts, events, or details.
- Do not claim to have opened or read a webpage.
- If a result only gives a website homepage, don't pretend it
  contains a specific story.
- Mention the source name for important claims.
- If the search results are insufficient, clearly say that.
- Keep the response concise but useful.

For news queries, use this format when possible:

LATEST NEWS

1. Headline
   Short summary.
   Source: Website

2. Headline
   Short summary.
   Source: Website

3. Headline
   Short summary.
   Source: Website

Do not use citation markers such as [1], [2], or 【1】.
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

        # =========================
        # SEARCH AI ERROR
        # =========================

        if response.status_code != 200:

            print(
                "SEARCH AI ERROR:",
                response.status_code,
                response.text
            )

            output = f"Search results for: {query}\n\n"

            for i, result in enumerate(results, 1):
                output += (
                    f"{i}. {result['title']}\n"
                    f"{result['snippet']}\n"
                    f"Source: {result['url']}\n\n"
                )

            return output.strip()

        data = response.json()

        answer = (
            data
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )

        if answer:
            return answer.strip()

        return f"Search completed, but AJ couldn't summarize the results."

    except Exception as error:

        print("WEB SEARCH ERROR:", error)

        return "AJ could not perform the web search right now."


# =========================
# AJ AI BRAIN
# =========================

def ask_aj(message, history=None):

    message = message.strip()

    if not message:
        return "Please say something."

    lower = message.lower()

    # =========================================================
    # AJ COMMAND CENTER
    # =========================================================

    command_result = handle_command(message)

    if command_result is not None:

        if command_result.startswith("__AJ_MODE_STUDY__"):

            message = (
                "Study mode. Explain the following for a B.Tech "
                "student with clear concepts, examples, and "
                "exam-ready points:\n"
                + command_result.replace(
                    "__AJ_MODE_STUDY__",
                    "",
                    1
                )
            )

        elif command_result.startswith("__AJ_MODE_CODING__"):

            message = (
                "Coding mode. Solve the following professionally. "
                "Give correct code, explanation, and a small example:\n"
                + command_result.replace(
                    "__AJ_MODE_CODING__",
                    "",
                    1
                )
            )

        else:
            return command_result

    # =========================
    # BASIC COMMANDS
    # =========================

    if lower in ["bye", "exit"]:
        return "Goodbye, Ajay."

    # =========================
    # CLEAR MEMORY
    # =========================

    if lower in [
        "clear memory",
        "forget everything",
        "delete my memory"
    ]:

        clear_memory()

        return "Your saved AJ memory has been cleared."

    # =========================
    # SHOW MEMORY
    # =========================

    if lower in [
        "what do you remember about me",
        "what do you remember",
        "show my memory",
        "show memory",
        "my memories"
    ]:

        memory = get_all_memory()

        if not memory:
            return "I don't have any saved personal memories yet."

        return (
            "Here is what I remember:\n\n"
            + build_memory_text()
        )

    # =========================
    # FORGET
    # =========================

    forgotten = forget_memory(message)

    if forgotten:
        return forgotten

    # =========================
    # SAVE MEMORY
    # =========================

    process_memory(message)


    if lower.startswith("open "):
        site = lower[5:].strip()

        if site in websites:

            return (
                f"Opening {site.title()}:\n\n"
                f"{websites[site]}"
            )

        return (
            f"I don't have a direct link for {site} yet."
        )

    # WEB SEARCH
    # =========================

    if lower.startswith("search for ") or lower.startswith("search "):

        if lower.startswith("search for "):
            query = message[11:].strip()
        else:
            query = message[7:].strip()

        if not query:
            return "What would you like me to search for?"

        return web_search(query)

    # =========================
    # TIME
    # =========================

    if (
        "what time is it" in lower
        or lower == "time"
    ):

        return (
            f"The current time is "
            f"{datetime.now().strftime('%I:%M %p')}."
        )

    # =========================
    # DATE
    # =========================

    if (
        "today's date" in lower
        or lower == "date"
    ):

        return (
            f"Today is "
            f"{datetime.now().strftime('%d %B %Y')}."
        )

    # =========================
    # API KEY
    # =========================

    if not OPENROUTER_API_KEY:

        return (
            "OpenRouter API key is not connected. "
            "Please check the GitHub secret."
        )

    # =========================
    # HISTORY + MEMORY
    # =========================

    history = history or []

    memory_text = build_memory_text()

    messages = [
        {
            "role": "system",
            "content": f"""
You are AJ, a personal AI assistant created by Ajay.

Your name is AJ.
The user's name is Ajay.

Be intelligent, helpful, accurate and concise.

Use saved memory and recent conversation when relevant.

MEMORY RULES:

1. Saved memory belongs to Ajay.
2. Use memory only when relevant.
3. Never invent memories.
4. If memory doesn't contain an answer, don't claim it does.
5. Do not pretend to remember something that isn't saved.

SAVED MEMORY:

{memory_text}
"""
        }
    ]

    # =========================
    # RECENT HISTORY
    # =========================

    for item in history[-10:]:

        role = item.get("role")
        content = item.get("content")

        if role in ["user", "assistant"] and content:

            messages.append({
                "role": role,
                "content": content
            })

    # =========================
    # CURRENT MESSAGE
    # =========================

    messages.append({
        "role": "user",
        "content": message
    })

    # =========================
    # OPENROUTER
    # =========================

    try:

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
                "messages": messages
            },
            timeout=60
        )

        if response.status_code != 200:

            print(
                "OPENROUTER ERROR:",
                response.status_code,
                response.text
            )

            if response.status_code == 401:
                return (
                    "AJ cannot authenticate with OpenRouter. "
                    "Please check the API key."
                )

            if response.status_code == 429:
                return (
                    "AJ could not get a response from the available "
                    "OpenRouter models right now. The fallback models "
                    "are also unavailable or rate-limited. Please try "
                    "again shortly."
                )

            return (
                "AJ's AI service returned an error. "
                "Please try again."
            )

        data = response.json()

        answer = (
            data
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )

        if answer:
            return answer.strip()

        return "AJ did not receive a valid AI response."

    except requests.exceptions.Timeout:

        return "AJ's AI service took too long to respond."

    except requests.exceptions.RequestException as error:

        print("OPENROUTER CONNECTION ERROR:", error)

        return "AJ is having trouble connecting to the AI service."

    except Exception as error:

        print("AJ ERROR:", error)

        return "AJ encountered an unexpected error."


# =========================
# TERMINAL MODE
# =========================

if __name__ == "__main__":

    print("================================")
    print("        AJ AI ASSISTANT")
    print("================================")
    print("AJ is online.")
    print("AI Provider: OpenRouter")
    print("Model:", MODEL)
    print("Persistent memory: ON")
    print("Web search: ON")
    print("================================")

    history = []

    while True:

        user_message = input("You: ").strip()

        if user_message.lower() == "exit":

            print("AJ: Goodbye, Ajay.")
            break

        answer = ask_aj(
            user_message,
            history
        )

        print("AJ:", answer)

        history.append({
            "role": "user",
            "content": user_message
        })

        history.append({
            "role": "assistant",
            "content": answer
        })
