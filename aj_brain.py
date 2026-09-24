import os
import json
import requests

from aj_memory import (
    remember,
    get_all_memory,
    clear_memory,
    save_memory
)

from aj_tools import run_command


# ============================================================
# AJ CONFIGURATION
# ============================================================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)

MODEL = "openrouter/free"

conversation_history = []


# ============================================================
# AJ SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are AJ, a general-purpose personal AI assistant.

Your name is AJ.

You were created by Ajay Bollipo.

Your job is to answer questions accurately, clearly,
naturally and efficiently.

You can help with:

- General knowledge
- Science
- Mathematics
- Engineering
- Programming
- Computer science
- AI and machine learning
- College studies
- Projects
- Writing
- Translation
- History
- Geography
- Technology
- Business
- Research
- Everyday questions
- Problem solving

ACCURACY RULES:

1. Never intentionally invent facts.

2. If current web information is supplied, use it.

3. Do not claim to have searched the web unless a search
   was actually performed.

4. If information is uncertain, say so.

5. If sources disagree, explain the disagreement.

6. Never fabricate sources, URLs, statistics or quotes.

7. For mathematics, calculate carefully.

8. For programming, provide practical working code.

9. For academic questions, explain clearly.

10. Answer directly before giving unnecessary detail.

11. Use memory only when it is relevant.

12. Never claim an action happened unless a tool confirms it.
"""


# ============================================================
# OPENROUTER
# ============================================================

def ask_openrouter(messages, max_tokens=1000):

    if not OPENROUTER_API_KEY:
        return "OpenRouter API key is not configured."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/",
        "X-Title": "AJ Personal AI"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": max_tokens
    }

    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=45
    )

    response.raise_for_status()

    data = response.json()

    try:
        return (
            data["choices"][0]["message"]["content"]
            .strip()
        )

    except (KeyError, IndexError, TypeError):

        return "I received an unexpected AI response."


# ============================================================
# WEB SEARCH
# ============================================================

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


def web_search(query, max_results=5):

    if DDGS is None:
        return []

    try:

        results = []

        with DDGS() as ddgs:

            items = ddgs.text(
                query,
                max_results=max_results
            )

            for item in items:

                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", "")
                })

        return results

    except Exception as error:

        print("WEB SEARCH ERROR:", error)

        return []


# ============================================================
# EXPLICIT SEARCH DETECTION
# ============================================================

def extract_search_query(message):

    text = message.strip()
    lower = text.lower()

    prefixes = [
        "search the web for ",
        "search web for ",
        "search for ",
        "search ",
        "look up ",
        "find information about ",
        "find info about ",
        "google "
    ]

    for prefix in prefixes:

        if lower.startswith(prefix):

            query = text[len(prefix):].strip()

            if query:
                return query

    return None


# ============================================================
# FAST CURRENT-INFORMATION DETECTION
# ============================================================

def needs_web_search(message):

    lower = message.lower().strip()

    # Current-time words
    current_words = [
        "today",
        "tonight",
        "yesterday",
        "tomorrow",
        "right now",
        "currently",
        "current",
        "latest",
        "recent",
        "recently",
        "newest",
        "this week",
        "this month",
        "breaking",
        "live",
        "update",
        "updates"
    ]

    # Live information topics
    live_topics = [
        "weather",
        "temperature",
        "news",
        "stock price",
        "share price",
        "market price",
        "crypto price",
        "bitcoin price",
        "cricket score",
        "football score",
        "match score",
        "election result",
        "election results",
        "exam result",
        "result today"
    ]

    if any(
        word in lower
        for word in current_words
    ):
        return True

    if any(
        phrase in lower
        for phrase in live_topics
    ):
        return True

    return False


# ============================================================
# RESEARCH DETECTION
# ============================================================

def is_research_question(message):

    lower = message.lower()

    phrases = [
        "research",
        "deep research",
        "investigate",
        "compare",
        "comparison",
        "pros and cons",
        "advantages and disadvantages",
        "detailed analysis",
        "in detail",
        "fact check",
        "fact-check",
        "verify this",
        "with sources"
    ]

    return any(
        phrase in lower
        for phrase in phrases
    )


# ============================================================
# SOURCE TEXT
# ============================================================

def build_source_text(results):

    parts = []

    for index, item in enumerate(
        results,
        1
    ):

        parts.append(
            f"""
SOURCE {index}

Title:
{item.get("title", "")}

URL:
{item.get("url", "")}

Summary:
{item.get("snippet", "")}
"""
        )

    return "\n".join(parts)


# ============================================================
# ANSWER USING WEB RESULTS
# ============================================================

def answer_from_web(
    query,
    results
):

    if not results:

        return (
            "I couldn't find reliable web information "
            f"for: {query}"
        )

    source_text = build_source_text(
        results
    )

    research_mode = is_research_question(
        query
    )

    if research_mode:

        instruction = """
Research the question using the supplied sources.

Compare the sources where useful.

Do not invent unsupported information.

Mention important uncertainty or disagreement.

Give a clear, useful answer.

Include the most relevant source URLs.
"""

    else:

        instruction = """
Answer the question using the supplied sources.

Prefer information supported by multiple sources
when possible.

Do not invent unsupported information.

Keep the answer concise and useful.

Include the most relevant source URLs.
"""

    prompt = f"""
USER QUESTION:

{query}

WEB SOURCES:

{source_text}

TASK:

{instruction}
"""

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    try:

        return ask_openrouter(
            messages,
            max_tokens=1200
        )

    except Exception as error:

        print(
            "WEB ANSWER ERROR:",
            error
        )

        first = results[0]

        return (
            f"{first.get('title', '')}\n\n"
            f"{first.get('snippet', '')}\n\n"
            f"{first.get('url', '')}"
        )


# ============================================================
# MEMORY COMMANDS
# ============================================================

def handle_memory_command(message):

    lower = message.lower().strip()

    if (
        "what do you remember about me" in lower
        or "what do you remember" in lower
        or "show my memory" in lower
    ):

        memory = get_all_memory()

        if not memory:
            return (
                "I don't have anything stored "
                "in memory yet."
            )

        lines = []

        for key, value in memory.items():

            lines.append(
                f"{key}: {value}"
            )

        return (
            "Here is what I remember:\n"
            + "\n".join(lines)
        )

    if (
        "clear all memory" in lower
        or "forget everything" in lower
    ):

        clear_memory()

        return "All stored memory has been cleared."

    if lower.startswith("forget "):

        key = message[7:].strip()

        memory = get_all_memory()

        if key in memory:

            del memory[key]

            save_memory(memory)

            return f"I forgot {key}."

        return (
            f"I don't have {key} "
            "stored in memory."
        )

    return None


# ============================================================
# SAVE MEMORY
# ============================================================

def try_save_memory(message):

    lower = message.lower().strip()

    prefixes = [
        "remember that ",
        "remember ",
        "save that ",
        "save "
    ]

    matched = None

    for prefix in prefixes:

        if lower.startswith(prefix):

            matched = prefix
            break

    if not matched:
        return None

    content = message[len(matched):].strip()

    if not content:
        return (
            "What would you like me to remember?"
        )

    separators = [
        " is ",
        " are ",
        " = ",
        ":"
    ]

    for separator in separators:

        if separator in content:

            key, value = content.split(
                separator,
                1
            )

            key = key.strip()
            value = value.strip()

            if key and value:

                remember(
                    key,
                    value
                )

                return (
                    f"I'll remember that "
                    f"{key} is {value}."
                )

    remember(
        "note",
        content
    )

    return (
        f"I'll remember: {content}"
    )


# ============================================================
# AJ IDENTITY
# ============================================================

def is_creator_question(lower):

    phrases = [
        "who created you",
        "who created u",
        "who made you",
        "who made u",
        "who is your creator",
        "who's your creator",
        "who is ur creator",
        "who built you",
        "who built u",
        "who developed you",
        "who developed u",
        "who is your developer",
        "who is your owner"
    ]

    return any(
        phrase in lower
        for phrase in phrases
    )


def is_name_question(lower):

    phrases = [
        "what is your name",
        "what's your name",
        "who are you",
        "tell me your name",
        "your name"
    ]

    return any(
        phrase in lower
        for phrase in phrases
    )


# ============================================================
# TOOL RESULT
# ============================================================

def process_tool(message):

    try:

        tool_result = run_command(
            message
        )

        if not tool_result.get(
            "handled"
        ):
            return None

        result = tool_result.get(
            "result"
        )

        if not result:
            return None

        message_text = result.get(
            "message",
            ""
        )

        url = result.get(
            "url"
        )

        if url:

            return (
                f"{message_text}\n"
                f"{url}"
            )

        return message_text

    except Exception as error:

        print(
            "TOOL ERROR:",
            error
        )

        return None


# ============================================================
# AJ MAIN BRAIN
# ============================================================

def ask_aj(
    message,
    history=None
):

    global conversation_history

    if not message:
        return "Please say something."

    text = message.strip()
    lower = text.lower()

    # --------------------------------------------------------
    # IDENTITY
    # --------------------------------------------------------

    if is_creator_question(lower):

        return (
            "I was created by Ajay Bollipo "
            "as a personal AI assistant project. "
            "My name is AJ."
        )

    if is_name_question(lower):

        return "My name is AJ."

    # --------------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------------

    if lower in [
        "exit",
        "quit",
        "shutdown aj",
        "stop aj"
    ]:

        return "AJ is standing by."

    # --------------------------------------------------------
    # MEMORY
    # --------------------------------------------------------

    memory_response = handle_memory_command(
        text
    )

    if memory_response:
        return memory_response

    memory_saved = try_save_memory(
        text
    )

    if memory_saved:
        return memory_saved

    # --------------------------------------------------------
    # FAST LOCAL TOOLS
    # --------------------------------------------------------

    tool_response = process_tool(
        text
    )

    if tool_response:
        return tool_response

    # --------------------------------------------------------
    # EXPLICIT WEB SEARCH
    # --------------------------------------------------------

    search_query = extract_search_query(
        text
    )

    if search_query:

        results = web_search(
            search_query,
            max_results=6
        )

        return answer_from_web(
            search_query,
            results
        )

    # --------------------------------------------------------
    # AUTOMATIC CURRENT INFORMATION
    # --------------------------------------------------------

    if needs_web_search(text):

        results = web_search(
            text,
            max_results=6
        )

        if results:

            return answer_from_web(
                text,
                results
            )

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    if history:

        conversation_history = []

        for item in history[-10:]:

            role = item.get(
                "role"
            )

            content = item.get(
                "content"
            )

            if role and content:

                conversation_history.append({
                    "role": role,
                    "content": content
                })

    # --------------------------------------------------------
    # MEMORY CONTEXT
    # --------------------------------------------------------

    memory = get_all_memory()

    memory_context = ""

    if memory:

        memory_context = (
            "\n\nRelevant stored memory:\n"
            + json.dumps(
                memory,
                ensure_ascii=False
            )
        )

    # --------------------------------------------------------
    # NORMAL AI
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content":
                SYSTEM_PROMPT
                + memory_context
        }
    ]

    messages.extend(
        conversation_history[-10:]
    )

    messages.append({
        "role": "user",
        "content": text
    })

    try:

        answer = ask_openrouter(
            messages,
            max_tokens=1000
        )

    except Exception as error:

        print(
            "OPENROUTER ERROR:",
            error
        )

        return (
            "I'm having trouble connecting "
            "to my AI brain right now."
        )

    # --------------------------------------------------------
    # SAVE CONVERSATION
    # --------------------------------------------------------

    conversation_history.append({
        "role": "user",
        "content": text
    })

    conversation_history.append({
        "role": "assistant",
        "content": answer
    })

    if len(
        conversation_history
    ) > 20:

        conversation_history = (
            conversation_history[-20:]
        )

    return answer


# ============================================================
# TERMINAL MODE
# ============================================================

if __name__ == "__main__":

    print()
    print("================================")
    print("          AJ AI ASSISTANT")
    print("================================")
    print("AJ is online.")
    print("AI Provider: OpenRouter")
    print(f"Model: {MODEL}")
    print("Memory: ON")
    print("Web Search: ON")
    print("Automatic Current Info: ON")
    print("Action Engine: ON")
    print("Universal Question Mode: ON")
    print("================================")
    print()

    while True:

        try:

            user_input = input(
                "You: "
            )

            if not user_input.strip():
                continue

            response = ask_aj(
                user_input
            )

            print(
                f"AJ: {response}"
            )

            print()

            if user_input.lower().strip() in [
                "exit",
                "quit",
                "shutdown aj",
                "stop aj"
            ]:
                break

        except KeyboardInterrupt:

            print(
                "\nAJ: Standing by."
            )

            break

        except Exception as error:

            print(
                "ERROR:",
                error
            )