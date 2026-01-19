# main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os, itertools, io, base64
import pdfplumber
from PIL import Image

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================== API KEYS ==================
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
MODEL = "gemini-2.5-flash-lite"

def get_model():
    genai.configure(api_key=next(key_cycle))
    return genai.GenerativeModel(MODEL)

def lang_instruction(lang):
    return "Write output in clear academic English." if lang == "en" else "اكتب الناتج باللغة العربية الفصحى."

# ================== UTILS ==================
def pdf_text(b: bytes):
    text = ""
    with pdfplumber.open(io.BytesIO(b)) as pdf:
        for p in pdf.pages:
            if p.extract_text():
                text += p.extract_text() + "\n"
    return text.strip()

def image_bytes(b: bytes):
    img = Image.open(io.BytesIO(b))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ================== MODELS ==================
class AskRequest(BaseModel):
    prompt: str
    language: str = "ar"

# ================== ENDPOINTS ==================
@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    model = get_model()
    prompt = f"""
{lang_instruction(req.language)}

أنشئ اختبار اختيار من متعدد من الموضوع التالي.

قواعد:
- 4 خيارات
- شرح موسع للإجابة الصحيحة
- شرح مختصر للخاطئة
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
    language: str = Form("ar")
):
    b = await file.read()
    model = get_model()

    if file.filename.lower().endswith(".pdf"):
        text = pdf_text(b)
        if not text:
            raise HTTPException(400, "PDF has no text")
        content = text
        img = None
    else:
        img = image_bytes(b)
        content = None

    if mode == "summary":
        prompt = f"""
{lang_instruction(language)}

لخص المحتوى التالي بدون تكرار:
- دمج الأفكار
- تنظيم
- أسلوب تعليمي

الناتج:
1. ملخص عام
2. أفكار رئيسية
3. نقاط مهمة
4. خلاصة
"""
        if content:
            r = model.generate_content(prompt + "\n" + content[:12000])
        else:
            r = model.generate_content([prompt, {"mime_type": file.content_type, "data": img}])
        return {"result": r.text}

    prompt = f"""
{lang_instruction(language)}

أنشئ أسئلة تعليمية اختيار من متعدد:
- 4 خيارات
- شرح موسع للصحيح
- شرح مختصر للخاطئ
- لا تكرر الأفكار
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
    if content:
        r = model.generate_content(prompt + "\n" + content[:12000])
    else:
        r = model.generate_content([prompt, {"mime_type": file.content_type, "data": img}])
    return {"result": r.text}