from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os, itertools, io, json
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

MODEL = "gemini-2.5-flash-lite"
MAX_TOTAL_QUESTIONS = 60

keys = [os.getenv(f"GEMINI_KEY_{i}") for i in range(1, 8)]
keys = [k for k in keys if k]
if not keys:
    raise RuntimeError("No Gemini API keys found")

key_cycle = itertools.cycle(keys)

def get_model():
    genai.configure(api_key=next(key_cycle))
    return genai.GenerativeModel(MODEL)

def lang_instruction(lang):
    return (
        "Write the output in clear academic English."
        if lang == "en"
        else "اكتب الناتج باللغة العربية الفصحى."
    )

def extract_pdf(data: bytes):
    text = ""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"
    return text.strip()

def prepare_image(data: bytes):
    img = Image.open(io.BytesIO(data))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

class ManualQuiz(BaseModel):
    prompt: str
    language: str = "ar"
    total_questions: int = 10

@app.get("/")
def root():
    return {"status": "ok"}

# ========== اختبار يدوي ==========
@app.post("/ask")
def manual_quiz(req: ManualQuiz):
    if req.total_questions > MAX_TOTAL_QUESTIONS:
        raise HTTPException(400, "Max 60 questions")

    model = get_model()

    prompt = f"""
{lang_instruction(req.language)}

أنشئ EXACTLY {req.total_questions} سؤال اختيار من متعدد.

قواعد:
- 4 خيارات
- شرح موسع للإجابة الصحيحة
- شرح مختصر لكل خيار خاطئ
- لا تكرار
- JSON فقط

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

# ========== ملف / صورة ==========
@app.post("/ask-file")
async def ask_file(
    file: UploadFile = File(...),
    mode: str = Form("questions"),
    language: str = Form("ar"),
    num_questions: int = Form(10)
):
    if num_questions > MAX_TOTAL_QUESTIONS:
        raise HTTPException(400, "Max 60 questions")

    data = await file.read()
    model = get_model()

    text, image = None, None
    name = file.filename.lower()

    if name.endswith(".pdf"):
        text = extract_pdf(data)
        if not text:
            raise HTTPException(400, "Empty PDF")
    elif name.endswith((".png", ".jpg", ".jpeg")):
        image = prepare_image(data)
    else:
        raise HTTPException(400, "Unsupported file")

    # ===== تلخيص =====
    if mode == "summary":
        prompt = f"""
{lang_instruction(language)}

لخص المحتوى التالي باحتراف:
- بدون تكرار
- أفكار مرتبة
- مناسب للملفات الكبيرة
"""
        r = (
            model.generate_content(prompt + text[:12000])
            if text
            else model.generate_content([prompt, {"mime_type": file.content_type, "data": image}])
        )
        return {"result": r.text}

    # ===== أسئلة =====
    prompt = f"""
{lang_instruction(language)}

أنشئ EXACTLY {num_questions} سؤال اختيار من متعدد من المحتوى التالي.

قواعد:
- 4 خيارات
- شرح موسع للإجابة الصحيحة
- شرح مختصر لكل خيار خاطئ
- لا تكرار
- JSON فقط

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

    r = (
        model.generate_content(prompt + text[:12000])
        if text
        else model.generate_content([prompt, {"mime_type": file.content_type, "data": image}])
    )

    return {"result": r.text}