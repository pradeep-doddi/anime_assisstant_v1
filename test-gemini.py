import os
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai

print("KEY:", os.getenv("GEMINI_API_KEY"))

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-flash-latest")

chat = model.start_chat()

response = chat.send_message("Say hello")

print("RESPONSE:", response.text)
