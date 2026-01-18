from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import json
import re
import fitz
from PIL import Image
import io
import pytesseract

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

MODEL_NAME = "gemini-2.5-flash-lite"

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

def clean_json(text: str):
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON found in model response")
    return json.loads(match.group())

def call_gemini(prompt: str):
    last_error = None
    for _ in range(len(keys)):
        try:
            api_key = next(key_cycle)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(prompt)
            return clean_json(response.text)
        except Exception as e:
            last_error = str(e)
    raise RuntimeError(last_error)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    try:
        result = call_gemini(req.prompt)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_text_from_pdf(file_bytes: bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def extract_text_from_image(file_bytes: bytes):
    image = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(image, lang="ara+eng")

@app.post("/ask-file")
async def ask_file(file: UploadFile = File(...)):
    try:
        content = await file.read()

        if file.content_type == "application/pdf":
            extracted_text = extract_text_from_pdf(content)
        elif file.content_type.startswith("image/"):
            extracted_text = extract_text_from_image(content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        prompt = f"""
أنشئ أسئلة اختبار اختيار من متعدد من النص التالي.
أعد النتيجة بصيغة JSON فقط وبدون أي شرح أو نص إضافي.

التنسيق:
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
{extracted_text}
"""

        result = call_gemini(prompt)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))