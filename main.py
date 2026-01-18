from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import base64
import fitz

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    model: str
    prompt: str

class AnalyzeRequest(BaseModel):
    file: str
    fileType: str
    mimeType: str
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
            return response.text
        except Exception as e:
            last_error = str(e)
    raise HTTPException(status_code=500, detail=last_error)

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

@app.post("/analyze-file")
def analyze_file(req: AnalyzeRequest):
    try:
        pdf_bytes = base64.b64decode(req.file)
        text = extract_text_from_pdf(pdf_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    last_error = None

    for _ in range(len(keys)):
        try:
            api_key = next(key_cycle)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(MODEL_NAME)

            full_prompt = f"""
أنت نظام توليد اختبارات تعليمية.
أرجع JSON فقط بدون أي شرح أو نص إضافي.

الصيغة المطلوبة:
{{
  "questions": [
    {{
      "q": "نص السؤال",
      "options": ["أ","ب","ج","د"],
      "answer": 0,
      "explanation": "شرح مختصر"
    }}
  ]
}}

النص:
{text}

{req.prompt}
"""

            response = model.generate_content(full_prompt)
            return response.text

        except Exception as e:
            last_error = str(e)

    raise HTTPException(status_code=500, detail=last_error)

@app.post("/ask-file")
async def ask_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = extract_text_from_pdf(content)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file")

    last_error = None

    for _ in range(len(keys)):
        try:
            api_key = next(key_cycle)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(MODEL_NAME)

            prompt = f"""
أنشئ 10 أسئلة اختيار من متعدد من النص التالي.
أرجع JSON فقط بنفس الصيغة:

{{
  "questions": [
    {{
      "q": "السؤال",
      "options": ["أ","ب","ج","د"],
      "answer": 0
    }}
  ]
}}

النص:
{text}
"""

            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            last_error = str(e)

    raise HTTPException(status_code=500, detail=last_error)