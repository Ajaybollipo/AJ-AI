import re


WAKE_WORDS = [
    "hey aj",
    "ok aj",
    "okay aj",
    "aj"
]


def remove_wake_word(text):
    """
    Remove AJ wake words from a voice command.
    """

    if not text:
        return ""

    cleaned = text.strip()

    for wake_word in WAKE_WORDS:

        pattern = (
            r"^\s*"
            + re.escape(wake_word)
            + r"[\s,.:!?-]*"
        )

        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE
        )

    return cleaned.strip()


def contains_wake_word(text):
    """
    Check whether a voice message starts
    with an AJ wake word.
    """

    if not text:
        return False

    cleaned = text.strip().lower()

    for wake_word in WAKE_WORDS:

        if cleaned == wake_word:
            return True

        if cleaned.startswith(
            wake_word + " "
        ):
            return True

        if cleaned.startswith(
            wake_word + ","
        ):
            return True

    return False


def process_voice_command(text):
    """
    Prepare a voice command for AJ.
    """

    if not text:

        return {
            "wake_word": False,
            "command": "",
            "active": False
        }

    has_wake_word = contains_wake_word(
        text
    )

    command = remove_wake_word(
        text
    )

    return {
        "wake_word": has_wake_word,
        "command": command,
        "active": has_wake_word or bool(command)
    }
