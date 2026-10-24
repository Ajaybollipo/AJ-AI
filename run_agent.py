
import json
import queue
import sys
import time
import webbrowser
from difflib import SequenceMatcher
from pathlib import Path
from math import gcd

import numpy as np
import sounddevice as sd
import pyttsx3
from scipy.signal import resample_poly
from vosk import Model, KaldiRecognizer

from aj_brain import ask_aj


# ==========================================
# AJ LOCAL VOICE AGENT
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models" / "vosk-model"

INPUT_DEVICE = 1
INPUT_RATE = 44100
INPUT_CHANNELS = 2
SAMPLE_RATE = 16000

WAKE_TIMEOUT = 10
WAKE_SIMILARITY = 0.72

audio_queue = queue.Queue()
conversation_history = []


WAKE_ALIASES = {
    # Original wake phrase and common recognition variations
    "hey aj",
    "hey a j",
    "hey age",
    "hey jay",
    "hey easy",
    "he easy",
    "hey eg",
    "he eg",
    "yeah aj",
    "yeah a j",
    "yeah age",
    "yeah eg",

    # Your preferred wake phrase
    "hey i am your boss",
    "hey i m your boss",
    "hey im your boss",
    "hey i am boss",
    "hey your boss",
    "hey i am the boss",
    "hey boss",
}

# ==========================================
# MICROPHONE
# ==========================================

def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"Microphone status: {status}", file=sys.stderr)

    audio_queue.put(bytes(indata))


def clear_audio_queue():
    while True:
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break


# ==========================================
# AJ VOICE
# ==========================================

def speak(text):
    """Speak a response using the installed system voice."""
    text = str(text).strip()

    if not text:
        return

    engine = None

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 178)
        engine.say(text)
        engine.runAndWait()

    except Exception as error:
        print(f"AJ speech error: {error}")

    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass


# ==========================================
# AUDIO CONVERSION
# ==========================================

def convert_audio(raw_audio):
    """Convert 44.1 kHz stereo int16 audio to 16 kHz mono int16."""
    audio = np.frombuffer(raw_audio, dtype=np.int16)

    if audio.size == 0:
        return b""

    # Ensure both stereo channels are present.
    audio = audio[:audio.size - (audio.size % INPUT_CHANNELS)]

    if audio.size == 0:
        return b""

    audio = audio.reshape(-1, INPUT_CHANNELS).astype(np.float32)

    # Stereo to mono.
    mono = audio.mean(axis=1)

    # Resample 44,100 Hz to 16,000 Hz.
    divisor = gcd(INPUT_RATE, SAMPLE_RATE)
    up = SAMPLE_RATE // divisor
    down = INPUT_RATE // divisor

    converted = resample_poly(mono, up, down)
    converted = np.clip(converted, -32768, 32767)

    return converted.astype(np.int16).tobytes()


# ==========================================
# SPEECH RECOGNITION
# ==========================================

def create_wake_recognizer(model):
    return KaldiRecognizer(model, SAMPLE_RATE)


def create_command_recognizer(model):
    return KaldiRecognizer(model, SAMPLE_RATE)


def normalize_text(text):
    return " ".join(
        "".join(
            char.lower() if char.isalnum() else " "
            for char in text
        ).split()
    )


def is_wake_phrase(text):
    normalized = normalize_text(text)

    if not normalized:
        return False

    if len(normalized.split()) > 6:
        return False

    if normalized in WAKE_ALIASES:
        return True

    for phrase in WAKE_ALIASES:
        similarity = SequenceMatcher(
            None,
            normalized,
            phrase
        ).ratio()

        if similarity >= WAKE_SIMILARITY:
            return True

    return False


# ==========================================
# LISTEN FOR A COMMAND
# ==========================================

def listen_for_command(model):
    recognizer = create_command_recognizer(model)
    deadline = time.monotonic() + WAKE_TIMEOUT

    print(
        f"AJ: Listening for your command "
        f"({WAKE_TIMEOUT} seconds)..."
    )

    while time.monotonic() < deadline:
        try:
            raw_audio = audio_queue.get(timeout=0.5)

        except queue.Empty:
            continue

        audio = convert_audio(raw_audio)

        if not audio:
            continue

        if recognizer.AcceptWaveform(audio):
            result = json.loads(recognizer.Result())
            command_text = result.get("text", "").strip()

            if command_text:
                return command_text

    # Retrieve any speech remaining when the timeout expires.
    result = json.loads(recognizer.FinalResult())

    return result.get("text", "").strip()


# ==========================================
# CONNECT TO AJ BRAIN
# ==========================================

def process_command(command_text):
    """
    Send the recognized command to AJ's existing brain.
    Handle direct URL commands and speak normal responses.
    """

    command_text = command_text.strip()

    if not command_text:
        speak("I didn't catch that, Boss.")
        return

    print(f"\nYou: {command_text}")
    print("AJ: Processing your request...")

    try:
        # Uses the existing AJ AI, commands and memory system.
        response = ask_aj(
            command_text,
            conversation_history
        )

        if response is None:
            response = "I couldn't generate a response, Boss."

        response = str(response).strip()

        # Save the conversation for follow-up questions.
        conversation_history.append({
            "role": "user",
            "content": command_text
        })

        conversation_history.append({
            "role": "assistant",
            "content": response
        })

        # Keep recent conversation history at a manageable size.
        del conversation_history[:-20]

        # Existing AJ brain uses this prefix for website commands.
        open_url_prefix = "__AJ_OPEN_URL__"

        if response.startswith(open_url_prefix):
            url = response[len(open_url_prefix):].strip()

            if (
                url.startswith("https://")
                or url.startswith("http://")
            ):
                opened = webbrowser.open(url)

                if opened:
                    message = "Opening it now, Boss."
                    print(f"AJ: {message}")
                    speak(message)
                else:
                    message = (
                        "I couldn't open the website automatically, "
                        "Boss. Please check your default browser."
                    )
                    print(f"AJ: {message}")
                    speak(message)

            else:
                message = (
                    "The website address returned by AJ "
                    "was invalid, Boss."
                )
                print(f"AJ: {message}")
                speak(message)

            return

        # Normal responses from AJ's brain.
        print(f"\nAJ: {response}\n")
        speak(response)

    except Exception as error:
        print(f"\nAJ command error: {error}")

        message = (
            "I encountered a problem processing that command, Boss. "
            "Please check the terminal for details."
        )

        speak(message)


# ==========================================
# MAIN AGENT
# ==========================================

def main():
    if not MODEL_DIR.is_dir():
        print("AJ speech model is missing.")
        print(f"Expected model folder: {MODEL_DIR}")
        return

    try:
        sd.check_input_settings(
            device=INPUT_DEVICE,
            samplerate=INPUT_RATE,
            channels=INPUT_CHANNELS,
            dtype="int16",
        )

    except Exception as error:
        print(f"Microphone settings error: {error}")
        print(
            "Check INPUT_DEVICE, INPUT_RATE and INPUT_CHANNELS "
            "against your microphone settings."
        )
        return

    print("Loading AJ speech model...")

    try:
        model = Model(str(MODEL_DIR))

    except Exception as error:
        print(f"Could not load the Vosk model: {error}")
        return

    recognizer = create_wake_recognizer(model)

    print("\nAJ is ready, Boss.")
    print('Say "Hey, I am your boss" to wake AJ.')
    print("Press Ctrl+C to stop.\n")

    try:
        with sd.RawInputStream(
            device=INPUT_DEVICE,
            samplerate=INPUT_RATE,
            blocksize=4096,
            dtype="int16",
            channels=INPUT_CHANNELS,
            callback=audio_callback,
        ):
            while True:
                raw_audio = audio_queue.get()
                audio = convert_audio(raw_audio)

                if not audio:
                    continue

                if not recognizer.AcceptWaveform(audio):
                    continue

                result = json.loads(recognizer.Result())
                spoken_text = result.get("text", "").strip()

                if not spoken_text:
                    continue

                print(f"Heard: {spoken_text}")

                if not is_wake_phrase(spoken_text):
                    continue

                clear_audio_queue()

                print("\nWake phrase detected.")
                print("AJ: Yes, Boss?")
                speak("Yes, Boss?")

                # Discard speech captured while AJ was speaking.
                clear_audio_queue()

                command_text = listen_for_command(model)

                if command_text:
                    print(f"Command captured: {command_text}")
                    process_command(command_text)

                else:
                    print("No command detected.")
                    speak("I didn't catch that, Boss.")

                clear_audio_queue()
                recognizer = create_wake_recognizer(model)

    except KeyboardInterrupt:
        print("\nAJ voice agent stopped, Boss.")

    except Exception as error:
        print(f"\nAJ encountered an error: {error}")
        print("Check your microphone permissions and audio device.")


if __name__ == "__main__":
    main()
