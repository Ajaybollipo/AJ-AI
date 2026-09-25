from datetime import datetime
import os
import requests
from aj_commands import handle_command

from aj_memory import remember, get_all_memory, clear_memory


# =========================
# OPENROUTER CONFIG
# =========================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openrouter/free"

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
    # =========================================================
    # CONVERSATION FOLLOW-UP MODE
    # =========================================================

    follow_up_instruction = detect_follow_up(
        message,
        history or []
    )

    if follow_up_instruction:
        message = build_conversation_prompt(
            message,
            history or [],
            follow_up_instruction
        )

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

        search_text = ""

        for i, result in enumerate(results, 1):

            search_text += (
                f"RESULT {i}\n"
                f"TITLE: {result['title']}\n"
                f"URL: {result['url']}\n"
                f"DESCRIPTION: {result['snippet']}\n\n"
            )

        if not OPENROUTER_API_KEY:

            output = f"Search results for: {query}\n\n"

            for i, result in enumerate(results, 1):
                output += (
                    f"{i}. {result['title']}\n"
                    f"{result['snippet']}\n"
                    f"Source: {result['url']}\n\n"
                )

            return output.strip()

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

        return "Search completed, but AJ couldn't summarize the results."

    except Exception as error:

        print("WEB SEARCH ERROR:", error)

        return "AJ could not perform the web search right now."


# =========================
# STUDY MODE
# =========================

def build_study_prompt(topic):
    return f"""
You are AJ Study Mode, a focused study assistant for Ajay.

The student asked about:

{topic}

Teach the topic clearly and in a B.Tech-student-friendly way.

Follow this structure when it fits the topic:

1. SIMPLE DEFINITION
2. CORE CONCEPT
3. IMPORTANT POINTS
4. STEP-BY-STEP EXPLANATION
5. EXAMPLE
6. EXAM-READY ANSWER
7. QUICK REVISION
8. 3 PRACTICE QUESTIONS

Rules:
- Start from basics if the topic may be unfamiliar.
- Use simple language.
- Keep technical terms accurate.
- Use headings and bullet points.
- For programming topics, include correct code when useful.
- For algorithms, explain the steps clearly.
- For numerical problems, show the calculation steps.
- For exam preparation, make the answer easy to revise.
- Do not invent syllabus-specific facts that were not provided.
- If the topic is ambiguous, explain the most common meaning and
  state what assumption you made.
"""


def build_quiz_prompt(topic):
    return f"""
You are AJ Quiz Mode.

Create a short quiz for a B.Tech student on:

{topic}

Rules:
- Ask 5 questions.
- Mix conceptual and application-based questions.
- Do not reveal answers immediately.
- Number every question.
- Keep the difficulty suitable for a college student.
- After the user answers, evaluate each answer and explain mistakes.
"""


def build_summary_prompt(topic):
    return f"""
You are AJ Revision Mode.

Summarize this study topic for a B.Tech student:

{topic}

Give:
- Definition
- 5 to 10 key points
- Important formulas/steps if applicable
- One small example
- Common exam points
- A 30-second quick revision section

Keep it concise and easy to memorize.
"""


def build_coding_prompt(request):
    return f"""
You are AJ Coding Assistant, a professional programming mentor.

The user asked:

{request}

Help the user solve the programming task accurately.

Follow this structure when useful:

1. UNDERSTAND THE PROBLEM
2. APPROACH
3. CODE
4. EXPLANATION
5. EXAMPLE / SAMPLE OUTPUT
6. COMPLEXITY
7. COMMON MISTAKES

Rules:
- Identify the programming language if the user specifies it.
- If no language is specified, use the language most appropriate
  for the request and clearly state it.
- Give complete, runnable code when code is requested.
- Preserve the user's intended behavior when fixing code.
- Explain errors in simple language.
- For debugging, identify the likely cause before giving the fix.
- For DSA questions, explain the algorithm and time/space complexity.
- For SQL, provide valid SQL and explain the query.
- For HTML/CSS/JavaScript, keep the code complete and practical.
- Never claim code was executed or tested unless it actually was.
- For exam questions, include a short exam-ready explanation.
"""


def detect_coding_request(message):
    lower = message.strip().lower()

    prefixes = (
        "write code for ",
        "write a program for ",
        "write a program to ",
        "generate code for ",
        "create code for ",
        "code for ",
        "solve this coding problem ",
        "solve this programming problem ",
        "debug this code ",
        "fix this code ",
        "fix my code ",
        "find the error in ",
        "find errors in ",
        "explain this code ",
        "explain my code ",
        "convert this code ",
        "optimize this code ",
        "program for ",
    )

    coding_keywords = (
        "python",
        "java",
        "c programming",
        "c++",
        "cpp",
        "javascript",
        "html",
        "css",
        "sql",
        "code",
        "program",
        "coding",
        "debug",
        "compiler error",
        "syntax error",
        "runtime error",
        "algorithm",
        "function",
        "class",
    )

    for prefix in prefixes:
        if lower.startswith(prefix):
            request = message[len(prefix):].strip()
            if request:
                return request

    if any(keyword in lower for keyword in coding_keywords):
        if any(
            action in lower
            for action in (
                "write",
                "create",
                "generate",
                "solve",
                "fix",
                "debug",
                "explain",
                "convert",
                "optimize",
                "error",
            )
        ):
            return message.strip()

    return None


def detect_study_request(message):
    lower = message.strip().lower()

    quiz_starts = (
        "quiz me on ",
        "quiz me about ",
        "test me on ",
        "test me about ",
        "give me a quiz on ",
        "give me a quiz about "
    )

    summary_starts = (
        "summarize ",
        "summarise ",
        "give me a summary of ",
        "summary of ",
        "revise ",
        "revision of "
    )

    study_starts = (
        "explain ",
        "teach me ",
        "teach me about ",
        "study ",
        "learn ",
        "help me understand ",
        "how does "
    )

    for prefix in quiz_starts:
        if lower.startswith(prefix):
            topic = message[len(prefix):].strip()
            if topic:
                return "quiz", topic

    for prefix in summary_starts:
        if lower.startswith(prefix):
            topic = message[len(prefix):].strip()
            if topic:
                return "summary", topic

    for prefix in study_starts:
        if lower.startswith(prefix):
            topic = message[len(prefix):].strip()
            if topic:
                return "study", topic

    return None, None


# =========================
# CONVERSATION INTELLIGENCE
# =========================

FOLLOW_UPS = {
    "why": "Explain why the previous answer is true, using the previous context.",
    "how": "Explain how the previous topic or solution works, using the previous context.",
    "how?": "Explain how the previous topic or solution works, using the previous context.",
    "why?": "Explain why the previous answer is true, using the previous context.",
    "explain again": "Explain the previous answer again in simpler language.",
    "explain that again": "Explain the previous topic again in simpler language.",
    "simplify that": "Simplify the previous answer without losing the important meaning.",
    "give example": "Give a clear example related to the previous topic.",
    "give me an example": "Give a clear example related to the previous topic.",
    "more": "Continue the previous answer with useful additional details.",
    "more details": "Continue the previous answer with useful additional details.",
    "what about it": "Continue discussing the previous topic using the existing context.",
    "what do you mean": "Clarify the previous answer in simple language.",
    "continue": "Continue from the previous answer without restarting the topic.",
}


def get_conversation_context(history):
    if not history:
        return "No recent conversation is available."

    context = []

    for item in history[-12:]:
        role = item.get("role")
        content = item.get("content")

        if role in ["user", "assistant"] and content:
            context.append(
                f"{role.upper()}: {content}"
            )

    if not context:
        return "No recent conversation is available."

    return "\n".join(context)


def detect_follow_up(message, history):
    if not history:
        return None

    normalized = " ".join(
        message.strip().lower().split()
    )

    if normalized in FOLLOW_UPS:
        return FOLLOW_UPS[normalized]

    short_follow_ups = (
        "and?",
        "then?",
        "next?",
        "really?",
        "why",
        "how",
        "example",
        "more"
    )

    if normalized in short_follow_ups:
        return (
            "Continue from the previous conversation. "
            "Do not restart the topic unless necessary."
        )

    return None


def build_conversation_prompt(message, history, follow_up_instruction):
    context = get_conversation_context(history)

    return f"""
You are AJ, a personal AI assistant.

The user is continuing an existing conversation.

RECENT CONVERSATION:
{context}

CURRENT USER MESSAGE:
{message}

CONVERSATION INSTRUCTION:
{follow_up_instruction}

Rules:
- Use the recent conversation to understand references such as
  "that", "it", "this", "why", "how", "again", and "more".
- Do not unnecessarily repeat the previous answer.
- Continue naturally from the existing topic.
- If the reference is genuinely ambiguous, ask one short
  clarification question.
- Keep the answer useful and concise.
"""


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

            message = build_study_prompt(
                command_result.replace(
                    "__AJ_MODE_STUDY__",
                    "",
                    1
                ).strip()
            )

        elif command_result.startswith("__AJ_MODE_CODING__"):

            message = (
                "Coding mode. Solve the following professionally. "
                "Give correct code, explanation, and a small example:\n\n"
                + command_result.replace(
                    "__AJ_MODE_CODING__",
                    "",
                    1
                ).strip()
            )

        elif command_result.startswith("__AJ_OPEN_URL__"):
            return command_result

        else:
            return command_result

    # =========================================================
    # NATURAL CODING MODE
    # =========================================================

    coding_request = detect_coding_request(message)

    if coding_request:
        message = build_coding_prompt(coding_request)

    # =========================================================
    # NATURAL STUDY MODE
    # =========================================================

    study_type, study_topic = detect_study_request(message)

    if study_type == "study":
        message = build_study_prompt(study_topic)

    elif study_type == "quiz":
        message = build_quiz_prompt(study_topic)

    elif study_type == "summary":
        message = build_summary_prompt(study_topic)

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

    # =========================
    # OPEN WEBSITE
    # =========================

    if lower.startswith("open "):
        site = lower[5:].strip()

        if site in websites:

            return (
                "__AJ_OPEN_URL__"
                + websites[site]
            )

        return f"I don't have a direct link for {site} yet."

    # =========================
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
            "Please check the Render environment variable."
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

CONVERSATION RULES:
1. Understand follow-up questions from recent context.
2. Resolve references such as "it", "that", "this", "again",
   "why", "how", "more", and "continue" from recent messages.
3. Do not repeat the same introduction when the user is continuing
   the same topic.
4. If the user changes the subject, follow the new subject.
5. Never invent conversation history that is not provided.

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
                    "AJ could not get a response from OpenRouter "
                    "right now. Please try again shortly."
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
    print("Study mode: ON")
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
