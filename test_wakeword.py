
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = (
    BASE_DIR / "models" / "openwakeword" / "hey_jarvis_v0.1.tflite"
)

SAMPLE_RATE = 16000
CHUNK_SIZE = 1280


def main():
    if not MODEL_PATH.is_file():
        print(f"Model not found: {MODEL_PATH}")
        return

    print("Loading wake-word detector...")
    detector = Model(
        wakeword_models=[str(MODEL_PATH)],
        inference_framework="onnx",
    )

    print('Ready! Say "Hey Jarvis" to test.')
    print("Press Ctrl+C to stop.\n")

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            dtype="int16",
            channels=1,
        ) as stream:
            while True:
                audio, _ = stream.read(CHUNK_SIZE)
                samples = np.frombuffer(audio, dtype=np.int16)
                predictions = detector.predict(samples)

                for name, score in predictions.items():
                    print(f"\r{name}: {score:.3f}   ", end="", flush=True)

                    if score >= 0.5:
                        print("\nWake word detected!")
                        detector.reset()

    except KeyboardInterrupt:
        print("\nTest stopped.")


if __name__ == "__main__":
    main()
