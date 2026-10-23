
import json
import queue
import sys
import time
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

# Common Vosk interpretations of "Hey AJ".
# These are transcript matches, not separate wake-word models.
WAKE_PHRASES = {
    "hey aj",
    "hey a j",
    "hey age",
    "hey jay",
    "hey easy",
    "hey eg",
    "yeah aj",
    "yeah a j",
    "yeah age",
    "yeah eg",
    "a j",
    "aj",
}

WAKE_GRAMMAR = json.dumps(
    sorted(WAKE_PHRASES) + ["[unk]"]
)

audio_queue = queue.Queue()


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
    """Recognizer restricted to likely wake-word transcripts."""
    return KaldiRecognizer(
        model,
        SAMPLE_RATE,
        WAKE_GRAMMAR,
    )


def create_command_recognizer(model):
    """Normal recognizer for spoken commands."""
    return KaldiRecognizer(model, SAMPLE_RATE)


def clear_audio_queue():
    while True:
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break


def normalize_text(text):
    """Normalize punctuation and spacing for transcript matching."""
    return " ".join(
        "".join(
            char.lower() if char.isalnum() else " "
            for char in text
        ).split()
    )


def is_wake_phrase(text):
    normalized = normalize_text(text)
    return normalized in WAKE_PHRASES


def listen_for_command(model):
    """Listen for one command for up to WAKE_TIMEOUT seconds."""
    recognizer = create_command_recognizer(model)
    deadline = time.monotonic() + WAKE_TIMEOUT
    command_text = ""

    print("AJ: Listening for your command...")

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

    final_result = json.loads(recognizer.FinalResult())
    return final_result.get("text", "").strip()


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
            blocksize=8000,
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

                # Reset wake recognition before AJ speaks.
                clear_audio_queue()
                recognizer = create_wake_recognizer(model)

                speak("Yes, Boss?")
                print("AJ: Yes, Boss?")

                # Give the microphone a moment after speech playback.
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
