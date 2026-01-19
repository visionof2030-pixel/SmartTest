from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import io
import pdfplumber
from PIL import Image
import math
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = "gemini-2.5-flash-lite"

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

def get_model():
    genai.configure(api_key=next(key_cycle))
    return genai.GenerativeModel(MODEL)

def lang_instruction(lang):
    return "Write the final output in clear academic English." if lang == "en" else "اكتب الناتج النهائي باللغة العربية الفصحى."

def extract_text_from_pdf(data: bytes):
    text = ""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t + "\n"
    return text.strip()

def prepare_image(data: bytes):
    img = Image.open(io.BytesIO(data))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def chunk_text(text, max_chars=4000):
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

def safe_json(text):
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

class AskRequest(BaseModel):
    prompt: str
    language: str = "ar"
    num_questions: int = 10

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    model = get_model()
    prompt = f"""
{lang_instruction(req.language)}

أنشئ {req.num_questions} سؤال اختيار من متعدد عن الموضوع التالي.

قواعد:
- 4 خيارات
- شرح موسع للصحيح
- شرح مختصر للخاطئ
- أعد JSON فقط

الصيغة:
{{
 "questions":[
  {{
   "q":"",
   "options":["","","",""],
   "answer":0,
   "explanations":["","","",""]
  }}
 ]
}}

الموضوع:
{req.prompt}
"""
    r = model.generate_content(prompt)
    return {"result": r.text}

@app.post("/ask-file")
async def ask_file(
    file: UploadFile = File(...),
    mode: str = Form("questions"),
    language: str = Form("ar"),
    num_questions: int = Form(10)
):
    data = await file.read()
    model = get_model()

    text = None
    image = None

    name = file.filename.lower()
    if name.endswith(".pdf"):
        text = extract_text_from_pdf(data)
        if not text:
            raise HTTPException(400, "PDF has no readable text")
    elif name.endswith((".png", ".jpg", ".jpeg")):
        image = prepare_image(data)
    else:
        raise HTTPException(400, "Unsupported file type")

    if mode == "summary":
        prompt = f"""
{lang_instruction(language)}

لخص المحتوى التالي بدون تكرار:
- دمج الأفكار
- تنظيم المحتوى
- أسلوب تعليمي

الناتج:
1. ملخص عام
2. أفكار رئيسية
3. نقاط مهمة
4. خلاصة
"""
        if text:
            r = model.generate_content(prompt + "\n" + text[:12000])
        else:
            r = model.generate_content([prompt, {"mime_type": file.content_type, "data": image}])
        return {"result": r.text}

    all_questions = []
    chunks = chunk_text(text, 4000) if text else [None]
    per_chunk = max(1, math.ceil(num_questions / len(chunks)))

    for chunk in chunks:
        if len(all_questions) >= num_questions:
            break

        prompt = f"""
{lang_instruction(language)}

أنشئ {per_chunk} سؤال اختيار من متعدد من المحتوى التالي.

قواعد صارمة:
- 4 خيارات
- شرح موسع للصحيح
- شرح مختصر للخاطئ
- لا تكرر الأسئلة
- أعد JSON فقط

الصيغة:
{{
 "questions":[
  {{
   "q":"",
   "options":["","","",""],
   "answer":0,
   "explanations":["","","",""]
  }}
 ]
}}
"""
        if chunk:
            r = model.generate_content(prompt + "\n" + chunk)
        else:
            r = model.generate_content([
                prompt,
                {"mime_type": file.content_type, "data": image}
            ])

        parsed = safe_json(r.text)
        all_questions.extend(parsed.get("questions", []))

    return {"result": json.dumps({"questions": all_questions[:num_questions]}, ensure_ascii=False)}