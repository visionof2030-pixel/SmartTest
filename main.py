from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import io
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
MAX_QUESTIONS = 60
MAX_TEXT_CHARS = 12000

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

def lang_instruction(lang: str):
    return (
        "Write the final output in clear academic English."
        if lang == "en"
        else "اكتب الناتج النهائي باللغة العربية الفصحى."
    )

def extract_text_from_pdf(data: bytes):
    text = ""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()

def prepare_image(data: bytes):
    img = Image.open(io.BytesIO(data))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

class ManualQuizRequest(BaseModel):
    prompt: str
    language: str = "ar"
    total_questions: int = 10

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def manual_quiz(req: ManualQuizRequest):
    if req.total_questions < 1 or req.total_questions > MAX_QUESTIONS:
        raise HTTPException(status_code=400, detail="Invalid number of questions")

    model = get_model()

    prompt = f"""
{lang_instruction(req.language)}

أنشئ {req.total_questions} سؤال اختيار من متعدد من الموضوع التالي.

قواعد صارمة:
- 4 خيارات لكل سؤال
- شرح موسع للإجابة الصحيحة
- شرح مختصر لكل خيار خاطئ
- لا تكرر الأفكار أو الأسئلة
- غطِّ الموضوع بالكامل
- أعد JSON فقط بدون أي رموز إضافية

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
    num_questions: int = Form(10),
):
    if num_questions < 1 or num_questions > MAX_QUESTIONS:
        raise HTTPException(status_code=400, detail="Invalid number of questions")

    data = await file.read()
    model = get_model()

    text = None
    image = None

    name = file.filename.lower()

    if name.endswith(".pdf"):
        extracted = extract_text_from_pdf(data)
        if extracted:
            text = extracted[:MAX_TEXT_CHARS]
        else:
            image = data
    elif name.endswith((".png", ".jpg", ".jpeg")):
        image = prepare_image(data)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if mode == "summary":
        prompt = f"""
{lang_instruction(language)}

لخص المحتوى التالي تلخيصًا احترافيًا منظمًا بصريًا.

قواعد:
- لا تكرار للأفكار
- كل فكرة مستقلة
- صياغة تعليمية واضحة
- بدون رموز مثل *** أو ###
- استخدم تنسيقًا نظيفًا

الناتج:
- ملخص عام
- الأفكار الرئيسية
- النقاط المهمة
- خلاصة نهائية
"""
        if text:
            r = model.generate_content(prompt + "\n" + text)
        else:
            r = model.generate_content(
                [
                    prompt,
                    {"mime_type": file.content_type, "data": image},
                ]
            )
        return {"result": r.text}

    prompt = f"""
{lang_instruction(language)}

أنشئ {num_questions} سؤال اختيار من متعدد من المحتوى التالي.

قواعد صارمة:
- 4 خيارات لكل سؤال
- شرح موسع للإجابة الصحيحة
- شرح مختصر لكل خيار خاطئ
- غطِّ جميع الأفكار المهمة
- لا تكرر الأسئلة
- أعد JSON فقط بدون أي نص إضافي

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

    if text:
        r = model.generate_content(prompt + "\n" + text)
    else:
        r = model.generate_content(
            [
                prompt,
                {"mime_type": file.content_type, "data": image},
            ]
        )

    return {"result": r.text}