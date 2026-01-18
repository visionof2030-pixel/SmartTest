from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools

app = FastAPI()

class AskRequest(BaseModel):
    model: str
    prompt: str

keys = [
    os.getenv("GEMINI_KEY_1"),
    os.getenv("GEMINI_KEY_2"),
    os.getenv("GEMINI_KEY_3"),
    os.getenv("GEMINI_KEY_4"),
    os.getenv("GEMINI_KEY_5"),
    os.getenv("GEMINI_KEY_6"),
    os.getenv("GEMINI_KEY_7"),
]

keys = [k for k in keys if k]
if not keys:
    raise RuntimeError("No Gemini API keys found in environment variables")

key_cycle = itertools.cycle(keys)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    last_error = None

    for _ in range(len(keys)):
        try:
            api_key = next(key_cycle)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(req.model)
            response = model.generate_content(req.prompt)
            return {"result": response.text}
        except Exception as e:
            last_error = str(e)
            continue

    raise HTTPException(status_code=500, detail=f"All keys failed: {last_error}")