import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

print("Modelos liberados na sua conta Groq:")
for modelo in client.models.list().data:
    print(f"- {modelo.id}")