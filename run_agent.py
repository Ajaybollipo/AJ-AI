
import json
import queue
import sys
import time
from pathlib import Path

import sounddevice as sd
import pyttsx3
from vosk import Model, KaldiRecognizer


# AJ LOCAL VOICE AGENT
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models" / "vosk-model"

SAMPLE_RATE = 16000
WAKE_PHRASES = (
    "hey aj",
    "hey a j",
    "okay aj",
    "ok aj",
)

audio_queue = queue.Queue()


def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"Microphone status: {status}", file=sys.stderr)

    audio_queue.put(bytes(indata))


def speak(text):
    """Speak a response through the Windows default voice."""
    engine = pyttsx3.init()
    engine.setProperty("rate", 178)
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def contains_wake_phrase(text):
    normalized = " ".join(
        text.lower().replace(",", " ").replace(".", " ").split()
    )
    return any(phrase in normalized for phrase in WAKE_PHRASES)


def clear_audio_queue():
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break


def main():
    if not MODEL_DIR.is_dir():
        print("AJ speech model is missing.")
        print(f"Expected model folder: {MODEL_DIR}")
        print("We will install the model in the next step.")
        return

    print("Loading AJ speech model...")
    model = Model(str(MODEL_DIR))

    recognizer = KaldiRecognizer(model, SAMPLE_RATE)

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

                if not contains_wake_phrase(spoken_text):
                    continue

                # Reset before AJ speaks so its reply isn't treated
                # as part of the wake phrase.
                clear_audio_queue()
                recognizer = KaldiRecognizer(model, SAMPLE_RATE)

                speak("Yes, Boss?")
                print("AJ: Yes, Boss? Listening for your command...")

                command_recognizer = KaldiRecognizer(
                    model, SAMPLE_RATE
                )

                command_text = ""
                deadline = time.monotonic() + 10

                while time.monotonic() < deadline:
                    try:
                        command_audio = audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    if command_recognizer.AcceptWaveform(command_audio):
                        command_result = json.loads(
                            command_recognizer.Result()
                        )
                        command_text = command_result.get(
                            "text", ""
                        ).strip()

                        if command_text:
                            break

                if not command_text:
                    command_result = json.loads(
                        command_recognizer.FinalResult()
                    )
                    command_text = command_result.get(
                        "text", ""
                    ).strip()

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
                recognizer = KaldiRecognizer(model, SAMPLE_RATE)

    except KeyboardInterrupt:
        print("\nAJ voice agent stopped, Boss.")

    except Exception as error:
        print(f"\nAJ encountered an error: {error}")
        print(
            "Check your microphone permissions and audio device."
        )


if __name__ == "__main__":
    main()
