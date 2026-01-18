from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
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
    raise RuntimeError("No Gemini API keys found")

key_cycle = itertools.cycle(keys)

MODEL_NAME = "gemini-2.5-flash-lite"

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

            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(req.prompt)

            return {"result": response.text}
        except Exception as e:
            last_error = str(e)

    raise HTTPException(status_code=500, detail=f"All keys failed: {last_error}")

@app.post("/ask-file")
async def ask_file(file: UploadFile = File(...)):
    last_error = None
    contents = await file.read()

    for _ in range(len(keys)):
        try:
            api_key = next(key_cycle)
            genai.configure(api_key=api_key)

            model = genai.GenerativeModel(MODEL_NAME)

            response = model.generate_content([
                {
                    "mime_type": file.content_type,
                    "data": contents
                },
                "اقرأ الملف وأنشئ أسئلة تعليمية عنه"
            ])

            return {"result": response.text}
        except Exception as e:
            last_error = str(e)

    raise HTTPException(status_code=500, detail=f"All keys failed: {last_error}")