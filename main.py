from fastapi import FastAPI
from pydantic import BaseModel
import google.generativeai as genai
import os

app = FastAPI()

class AskRequest(BaseModel):
    model: str
    prompt: str

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
async def ask(data: AskRequest):
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(data.model)
    response = model.generate_content(data.prompt)
    return {"result": response.text}