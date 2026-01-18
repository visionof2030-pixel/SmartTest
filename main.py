from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import fitz
from PIL import Image
import io
import json

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
    api_key = next(key_cycle)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    try:
        model = get_model()
        res = model.generate_content(req.prompt)
        return {"result": res.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page in doc:
        text += page.get_text()
    return text

def extract_text_from_image(file_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(file_bytes))
    model = get_model()
    res = model.generate_content([
        "استخرج النص من الصورة التالية بدقة:",
        img
    ])
    return res.text

@app.post("/ask-file")
async def ask_file(file: UploadFile = File(...)):
    try:
        data = await file.read()
        if file.content_type == "application/pdf":
            content = extract_text_from_pdf(data)
        elif file.content_type.startswith("image/"):
            content = extract_text_from_image(data)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        prompt = f"""
أنت معلم خبير في بناء الاختبارات التعليمية.

استخرج من النص التالي 10 أسئلة اختيار من متعدد.

شروط مهمة جدًا:
- كل سؤال يقيس الفهم لا الحفظ
- كل سؤال يحتوي على 4 خيارات
- حدد الإجابة الصحيحة
- التغذية الراجعة يجب أن تكون موسعة (3–6 أسطر) وتشمل:
  1. لماذا هذه الإجابة صحيحة
  2. لماذا الخيارات الأخرى خاطئة
  3. ربط المفهوم بمثال
  4. تبسيط الفكرة للطالب

النص:
{content}

صيغة الإخراج (JSON فقط دون أي شرح):

{{
  "questions": [
    {{
      "q": "",
      "options": ["", "", "", ""],
      "answer": 0,
      "explanation": ""
    }}
  ]
}}
"""

        model = get_model()
        res = model.generate_content(prompt)
        text = res.text.strip()

        json_start = text.find("{")
        json_text = text[json_start:]
        data = json.loads(json_text)

        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))