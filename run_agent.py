
import json
import queue
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

import sounddevice as sd
import pyttsx3
from vosk import Model, KaldiRecognizer


# ==========================================
# AJ LOCAL VOICE AGENT
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models" / "vosk-model"

SAMPLE_RATE = 16000
WAKE_TIMEOUT = 10
WAKE_SIMILARITY = 0.72

audio_queue = queue.Queue()


# Common Vosk misrecognitions of "Hey AJ".
# Short phrases only are considered for wake detection.
WAKE_ALIASES = {
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
}


def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"Microphone status: {status}", file=sys.stderr)

    audio_queue.put(bytes(indata))


def speak(text):
    """Speak through the Windows default voice."""
    engine = pyttsx3.init()
    engine.setProperty("rate", 178)
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def create_wake_recognizer(model):
    # Use normal recognition to avoid grammar restrictions
    # forcing inaccurate transcripts.
    return KaldiRecognizer(model, SAMPLE_RATE)


def create_command_recognizer(model):
    return KaldiRecognizer(model, SAMPLE_RATE)


def clear_audio_queue():
    while True:
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break


def normalize_text(text):
    return " ".join(
        "".join(
            char.lower() if char.isalnum() else " "
            for char in text
        ).split()
    )


def is_wake_phrase(text):
    """
    Match only short transcripts against known wake phrases.
    Longer sentences are ignored to reduce false activations.
    """
    normalized = normalize_text(text)

    if not normalized:
        return False

    words = normalized.split()

    # Do not wake on an entire unrelated sentence.
    if len(words) > 3:
        return False

    if normalized in WAKE_ALIASES:
        return True

    # Allow small recognition differences for short phrases.
    # The threshold reduces accidental matches but cannot
    # eliminate false activations.
    for phrase in WAKE_ALIASES:
        similarity = SequenceMatcher(
            None, normalized, phrase
        ).ratio()

        if similarity >= WAKE_SIMILARITY:
            return True

    return False


def listen_for_command(model):
    recognizer = create_command_recognizer(model)
    deadline = time.monotonic() + WAKE_TIMEOUT

    print(f"AJ: Listening for your command ({WAKE_TIMEOUT} seconds)...")

    while time.monotonic() < deadline:
        try:
            audio = audio_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if recognizer.AcceptWaveform(audio):
            result = json.loads(recognizer.Result())
            command_text = result.get("text", "").strip()

            if command_text:
                return command_text

    result = json.loads(recognizer.FinalResult())
    return result.get("text", "").strip()


def main():
    if not MODEL_DIR.is_dir():
        print("AJ speech model is missing.")
        print(f"Expected model folder: {MODEL_DIR}")
        return

    print("Loading AJ speech model...")
    model = Model(str(MODEL_DIR))

    recognizer = create_wake_recognizer(model)

    print("\nAJ is ready, Boss.")
    print('Say "Hey AJ" to wake AJ.')
    print("Press Ctrl+C to stop the microphone.\n")

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=4000,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            while True:
                data = audio_queue.get()

                if not recognizer.AcceptWaveform(data):
                    continue

                result = json.loads(recognizer.Result())
                spoken_text = result.get("text", "").strip()

                if not spoken_text:
                    continue

                print(f"Heard: {spoken_text}")

                if not is_wake_phrase(spoken_text):
                    continue

                # Clear pending microphone audio before responding.
                clear_audio_queue()

                print("\nWake phrase detected.")
                speak("Yes, Boss?")
                print("AJ: Yes, Boss?")

                # Discard audio captured while AJ was speaking.
                clear_audio_queue()

                command_text = listen_for_command(model)

                if command_text:
                    print(f"Command captured: {command_text}")
                    speak(
                        "I heard your command, Boss. "
                        "Command execution is not connected yet."
                    )
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
