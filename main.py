from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import io
import json
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
MAX_QUESTIONS_PER_CALL = 10
MAX_TOTAL_QUESTIONS = 60

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
    return "Write the final output in clear academic English." if lang == "en" else "اكتب الناتج النهائي باللغة العربية الفصحى."

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

class AskRequest(BaseModel):
    prompt: str
    language: str = "ar"
    total_questions: int = 10

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    if req.total_questions > MAX_TOTAL_QUESTIONS:
        raise HTTPException(status_code=400, detail="Maximum allowed questions is 60")

    model = get_model()
    prompt = f"""
{lang_instruction(req.language)}

أنشئ اختبار اختيار من متعدد من الموضوع التالي.

قواعد صارمة:
- أنشئ EXACTLY {req.total_questions} سؤالًا
- 4 خيارات لكل سؤال
- شرح موسع للإجابة الصحيحة
- شرح مختصر لكل خيار خاطئ
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

الموضوع:
{req.prompt}
"""
    r = model.generate_content(prompt)
    return json.loads(r.text)

@app.post("/ask-file")
async def ask_file(
    file: UploadFile = File(...),
    mode: str = Form("questions"),
    language: str = Form("ar"),
    num_questions: int = Form(10)
):
    if num_questions > MAX_TOTAL_QUESTIONS:
        raise HTTPException(status_code=400, detail="Maximum allowed questions is 60")

    data = await file.read()
    model = get_model()

    text = None
    image = None

    name = file.filename.lower()
    if name.endswith(".pdf"):
        text = extract_text_from_pdf(data)
        if not text:
            raise HTTPException(status_code=400, detail="PDF has no readable text")
    elif name.endswith((".png", ".jpg", ".jpeg")):
        image = prepare_image(data)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if mode == "summary":
        prompt = f"""
{lang_instruction(language)}

لخص المحتوى التالي بدون تكرار:
- دمج الأفكار المتشابهة
- تنظيم المحتوى
- صياغة تعليمية واضحة
- لا تطِل بدون فائدة

الناتج:
1. ملخص عام
2. الأفكار الرئيسية
3. النقاط المهمة
4. خلاصة نهائية
"""
        if text:
            r = model.generate_content(prompt + "\n" + text[:12000])
        else:
            r = model.generate_content([
                prompt,
                {"mime_type": file.content_type, "data": image}
            ])
        return {"summary": r.text}

    all_questions = []
    remaining = num_questions
    batch_index = 1

    while remaining > 0:
        batch_size = min(MAX_QUESTIONS_PER_CALL, remaining)

        batch_prompt = f"""
{lang_instruction(language)}

مهم جدًا:
- أنشئ EXACTLY {batch_size} سؤالًا فقط
- هذه الدفعة رقم {batch_index}
- لا تُكرر أي سؤال سابق

أنشئ {batch_size} سؤال اختيار من متعدد من المحتوى التالي.

قواعد صارمة:
- 4 خيارات لكل سؤال
- شرح موسع للإجابة الصحيحة
- شرح مختصر لكل خيار خاطئ
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

        if text:
            r = model.generate_content(batch_prompt + "\n" + text[:12000])
        else:
            r = model.generate_content([
                batch_prompt,
                {"mime_type": file.content_type, "data": image}
            ])

        try:
            parsed = json.loads(r.text)
            all_questions.extend(parsed["questions"])
        except Exception:
            break

        remaining -= batch_size
        batch_index += 1

    if len(all_questions) < num_questions:
        raise HTTPException(
            status_code=500,
            detail=f"Generated only {len(all_questions)} questions out of {num_questions}"
        )

    return {"questions": all_questions[:num_questions]}