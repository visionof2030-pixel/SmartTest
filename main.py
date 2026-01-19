from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os, itertools, io
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
    return (
        "Write the final output in clear academic English."
        if lang == "en"
        else "اكتب الناتج النهائي باللغة العربية الفصحى الواضحة."
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

class AskRequest(BaseModel):
    prompt: str
    language: str = "ar"
    total_questions: int = 10

@app.get("/")
def root():
    return {"status": "ok"}

# ---------- اختبار يدوي ----------
@app.post("/ask")
def ask(req: AskRequest):
    tq = min(max(req.total_questions, 5), 60)

    prompt = f"""
{lang_instruction(req.language)}

أنشئ {tq} سؤال اختيار من متعدد من الموضوع التالي.

قواعد صارمة:
- 4 خيارات لكل سؤال
- شرح موسع وعميق للإجابة الصحيحة
- شرح مختصر ومباشر لكل خيار خاطئ
- لا تكرر الأفكار
- مستوى تعليمي واضح
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
    model = get_model()
    r = model.generate_content(prompt)
    return {"result": r.text}

# ---------- من ملف ----------
@app.post("/ask-file")
async def ask_file(
    file: UploadFile = File(...),
    mode: str = Form("questions"),
    language: str = Form("ar"),
    num_questions: int = Form(10)
):
    num_questions = min(max(num_questions, 5), 60)
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

    # ---------- تلخيص ----------
    if mode == "summary":
        prompt = f"""
{lang_instruction(language)}

لخص المحتوى التالي بأسلوب تعليمي منسق بصريًا.

قواعد:
- كل فكرة في فقرة مستقلة
- لا تكرار
- لا رموز *** أو ----
- لغة واضحة
- مناسب للطلاب

المخرجات:
- عنوان
- فقرات ملونة (HTML spans)
- خلاصة نهائية
"""
        r = (
            model.generate_content(prompt + "\n" + text[:14000])
            if text
            else model.generate_content([prompt, {"mime_type": file.content_type, "data": image}])
        )
        return {"result": r.text}

    # ---------- Flash Cards ----------
    if mode == "flashcards":
        prompt = f"""
{lang_instruction(language)}

أنشئ بطاقات تعليمية Flash Cards من المحتوى التالي.

قواعد:
- فكرة واحدة لكل بطاقة
- لا تكرار
- صياغة تعليمية مختصرة
- أعد JSON فقط

الصيغة:
{{
 "cards":[
  {{
   "front":"",
   "back":""
  }}
 ]
}}
"""
        r = (
            model.generate_content(prompt + "\n" + text[:14000])
            if text
            else model.generate_content([prompt, {"mime_type": file.content_type, "data": image}])
        )
        return {"result": r.text}

    # ---------- أسئلة من ملف ----------
    prompt = f"""
{lang_instruction(language)}

أنشئ {num_questions} سؤال اختيار من متعدد من المحتوى التالي.

قواعد:
- 4 خيارات
- شرح موسع للإجابة الصحيحة
- شرح مختصر للخاطئة
- لا تكرر
- غطِّ جميع الأفكار
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
    r = (
        model.generate_content(prompt + "\n" + text[:14000])
        if text
        else model.generate_content([prompt, {"mime_type": file.content_type, "data": image}])
    )
    return {"result": r.text}