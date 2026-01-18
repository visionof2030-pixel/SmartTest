from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import fitz

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    model: str
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

def get_model(model_name: str):
    api_key = next(key_cycle)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    try:
        model = get_model(req.model)
        response = model.generate_content(req.prompt)
        return {"result": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def pdf_to_text(file_bytes: bytes) -> str:
    text = ""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page in doc:
        text += page.get_text()
    return text

@app.post("/ask-file")
async def ask_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        model_name = "gemini-2.5-flash-lite"
        model = get_model(model_name)

        if file.content_type == "application/pdf":
            text = pdf_to_text(content)
            prompt = f"""
أنشئ اختباراً من النص التالي بصيغة JSON فقط.

المطلوب:
- كل سؤال اختيار من متعدد (4 خيارات)
- لكل خيار شرح مختصر يوضح لماذا هو صحيح أو خاطئ
- شرح الخيار الصحيح يجب أن يكون موسعاً وتفصيلياً
- شروحات الخيارات الخاطئة تكون قصيرة
- لا تضف أي نص خارج JSON

الصيغة المطلوبة:
{{
  "questions": [
    {{
      "q": "نص السؤال",
      "options": ["أ","ب","ج","د"],
      "answer": 0,
      "explanations": [
        "شرح موسع للخيار الصحيح",
        "شرح مختصر لماذا هذا الخيار خاطئ",
        "شرح مختصر لماذا هذا الخيار خاطئ",
        "شرح مختصر لماذا هذا الخيار خاطئ"
      ]
    }}
  ]
}}

النص:
{text}
"""
            response = model.generate_content(prompt)
            return {"result": response.text}

        if file.content_type.startswith("image/"):
            prompt = """
حلل الصورة وأنشئ أسئلة اختيار من متعدد بصيغة JSON فقط بنفس الصيغة التالية:

{
  "questions": [
    {
      "q": "السؤال",
      "options": ["أ","ب","ج","د"],
      "answer": 0,
      "explanations": [
        "شرح موسع للخيار الصحيح",
        "شرح مختصر للخيار الخاطئ",
        "شرح مختصر للخيار الخاطئ",
        "شرح مختصر للخيار الخاطئ"
      ]
    }
  ]
}
"""
            response = model.generate_content([
                prompt,
                {"mime_type": file.content_type, "data": content}
            ])
            return {"result": response.text}

        raise HTTPException(status_code=400, detail="نوع الملف غير مدعوم")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))