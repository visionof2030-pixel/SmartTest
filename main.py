from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import tempfile
import fitz
import base64

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

def get_model():
    genai.configure(api_key=next(key_cycle))
    return genai.GenerativeModel(MODEL_NAME)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    try:
        model = get_model()
        response = model.generate_content(req.prompt)
        return {"result": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_text_from_pdf(path: str) -> str:
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

@app.post("/ask-file")
async def ask_file(file: UploadFile = File(...)):
    try:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        if suffix.lower() == ".pdf":
            content = extract_text_from_pdf(tmp_path)
        else:
            data = base64.b64encode(open(tmp_path, "rb").read()).decode()
            content = f"IMAGE_BASE64:{data}"

        prompt = f"""
حول المحتوى التالي إلى أسئلة اختبار بصيغة JSON فقط بدون أي شرح إضافي.

التنسيق الإجباري:
{{
  "questions": [
    {{
      "q": "نص السؤال",
      "options": ["أ", "ب", "ج", "د"],
      "answer": 0,
      "explanation": "شرح مختصر"
    }}
  ]
}}

المحتوى:
{content}
"""

        model = get_model()
        response = model.generate_content(prompt)
        return {"result": response.text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))