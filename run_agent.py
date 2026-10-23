
import json
import queue
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import sounddevice as sd
import pyttsx3
from scipy.signal import resample_poly
from math import gcd
from vosk import Model, KaldiRecognizer


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
    engine = pyttsx3.init()
    engine.setProperty("rate", 178)
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def convert_audio(raw_audio):
    """Convert 44.1 kHz stereo int16 audio to 16 kHz mono int16."""
    audio = np.frombuffer(raw_audio, dtype=np.int16)

    if audio.size == 0:
        return b""

    # Two interleaved channels -> mono.
    audio = audio[: audio.size - (audio.size % INPUT_CHANNELS)]
    if audio.size == 0:
        return b""

    audio = audio.reshape(-1, INPUT_CHANNELS).astype(np.float32)
    mono = audio.mean(axis=1)

    # Resample 44,100 Hz to 16,000 Hz.
    divisor = gcd(INPUT_RATE, SAMPLE_RATE)
    up = SAMPLE_RATE // divisor
    down = INPUT_RATE // divisor
    converted = resample_poly(mono, up, down)

    converted = np.clip(converted, -32768, 32767)
    return converted.astype(np.int16).tobytes()


def create_wake_recognizer(model):
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
    normalized = normalize_text(text)

    if not normalized:
        return False

    if len(normalized.split()) > 3:
        return False

    if normalized in WAKE_ALIASES:
        return True

    for phrase in WAKE_ALIASES:
        if SequenceMatcher(None, normalized, phrase).ratio() >= WAKE_SIMILARITY:
            return True

    return False


def listen_for_command(model):
    recognizer = create_command_recognizer(model)
    deadline = time.monotonic() + WAKE_TIMEOUT

    print(f"AJ: Listening for your command ({WAKE_TIMEOUT} seconds)...")

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

    result = json.loads(recognizer.FinalResult())
    return result.get("text", "").strip()


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
        return

    print("Loading AJ speech model...")
    model = Model(str(MODEL_DIR))
    recognizer = create_wake_recognizer(model)

    print("\nAJ is ready, Boss.")
    print('Say "Hey AJ" to wake AJ.')
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
                speak("Yes, Boss?")
                print("AJ: Yes, Boss?")

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
