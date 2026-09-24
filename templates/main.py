import pyttsx3

# Start AJ's voice
engine = pyttsx3.init()

engine.setProperty("rate", 175)
engine.setProperty("volume", 1.0)

print("================================")
print("          AJ AI")
print("================================")
print("AJ is online.")

engine.say("Hello Ajay. I am AJ. Your personal AI assistant is now online.")
engine.runAndWait()