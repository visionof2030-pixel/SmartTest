from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import base64
import tempfile
import pdfplumber

app = FastAPI()

# ================== Models ==================

class AskRequest(BaseModel):
    prompt: str
    model: str = "gemini-2.5-flash-lite"

class FileAnalyzeRequest(BaseModel):
    file: str
    fileType: str
    mimeType: str

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

def ask_gemini(prompt: str, model_name: str = "gemini-2.5-flash-lite"):
    last_error = None
    for _ in range(len(keys)):
        try:
            api_key = next(key_cycle)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            r = model.generate_content(prompt)
            return r.text
        except Exception as e:
            last_error = str(e)
    raise HTTPException(status_code=500, detail=f"All keys failed: {last_error}")

# ================== Utils ==================

def extract_text_from_pdf(b64: str) -> str:
    pdf_bytes = base64.b64decode(b64)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(pdf_bytes)
        path = f.name

    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()

# ================== Endpoints ==================

@app.get("/")
def root():
    return {"status": "ok"}

# --------- Manual Prompt ---------
@app.post("/ask")
def ask(req: AskRequest):
    result = ask_gemini(req.prompt, req.model)
    return {"result": result}

# --------- Analyze PDF (Questions) ---------
@app.post("/analyze-file")
def analyze_file(req: FileAnalyzeRequest):
    if req.fileType != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF supported")

    text = extract_text_from_pdf(req.file)

    prompt = f"""
أنت خبير تقويم تعليمي.
اقرأ النص التالي ثم أنشئ أسئلة تقيس الفهم العميق وليس الحفظ.

قواعد صارمة:
- لا تكرر نفس الفكرة بصياغة مختلفة
- كل سؤال يقيس فكرة مختلفة
- التغذية الراجعة للإجابة الصحيحة تكون موسعة ومفصلة
- التغذية الراجعة للإجابات الخاطئة مختصرة وتوضيحية
- الأسئلة تعليمية وليست مباشرة

أعد النتيجة JSON فقط بهذا الشكل:
{{
  "questions": [
    {{
      "q": "السؤال",
      "options": ["أ", "ب", "ج", "د"],
      "answer": 0,
      "explanation_correct": "شرح موسع للإجابة الصحيحة",
      "explanation_wrong": "سبب خطأ الخيارات الأخرى"
    }}
  ]
}}

النص:
{text}
"""

    result = ask_gemini(prompt)
    return {"result": result}

# --------- Summarize PDF (Smart Summary) ---------
@app.post("/summarize-file")
def summarize_file(req: FileAnalyzeRequest):
    if req.fileType != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF supported")

    text = extract_text_from_pdf(req.file)

    prompt = f"""
أنت خبير في التلخيص الأكاديمي الذكي.

مهمتك:
تلخيص النص التالي دون تكرار الأفكار مع دمج المتشابه منها.
لا تختصر بجمل قصيرة، بل قدم تلخيصاً تعليمياً منظمًا.

قواعد صارمة:
- لا تكرر نفس المعنى بصياغات مختلفة
- اجمع الأفكار المتشابهة في فكرة واحدة
- استخدم عناوين واضحة
- اجعل التلخيص تدريجياً من العام إلى الخاص
- لا تفقد أي فكرة جوهرية
- لا تضف معلومات غير موجودة
- استخدم أسلوب تعليمي موجه للطلاب

التنسيق المطلوب:
- عنوان رئيسي
- عناوين فرعية
- نقاط مركزة
- فقرات قصيرة واضحة

النص:
{text}
"""

    result = ask_gemini(prompt)
    return {"result": result}