from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import pdfplumber
from PIL import Image
import io
import base64

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class AskRequest(BaseModel):
    prompt: str

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

@app.post("/ask-file")
async def ask_file(file: UploadFile = File(...)):
    try:
        content = await file.read()

        if file.content_type == "application/pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = "\n".join(
                    [p.extract_text() for p in pdf.pages if p.extract_text()]
                )

            if not text.strip():
                raise HTTPException(status_code=400, detail="PDF has no readable text")

            prompt = f"""
            أنشئ أسئلة اختيار من متعدد من النص التالي.
            كل سؤال يحتوي:
            - سؤال واضح
            - 4 خيارات
            - الإجابة الصحيحة
            - شرح موسع للإجابة الصحيحة
            - شرح مختصر لماذا الخيارات الأخرى خاطئة

            أعد النتيجة بصيغة JSON فقط:
            {{
              "questions":[
                {{
                  "q":"",
                  "options":["","","",""],
                  "answer":0,
                  "explanation":""
                }}
              ]
            }}

            النص:
            {text[:12000]}
            """

            model = get_model()
            response = model.generate_content(prompt)
            return {"result": response.text}

        elif file.content_type.startswith("image/"):
            img = Image.open(io.BytesIO(content))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            model = get_model()
            response = model.generate_content([
                {"mime_type": "image/png", "data": img_b64},
                """
                استخرج أسئلة تعليمية من الصورة:
                - اختيار من متعدد
                - شرح موسع للإجابة الصحيحة
                - شرح مختصر للخيارات الخاطئة
                بنفس صيغة JSON
                """
            ])

            return {"result": response.text}

        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarize-file")
async def summarize_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = ""

        if file.content_type == "application/pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = "\n".join(
                    [p.extract_text() for p in pdf.pages if p.extract_text()]
                )

        elif file.content_type.startswith("image/"):
            img = Image.open(io.BytesIO(content))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            model = get_model()
            response = model.generate_content([
                {"mime_type": "image/png", "data": img_b64},
                """
                لخص محتوى الصورة تلخيصاً تعليمياً احترافياً:
                - ملخص عام
                - أفكار رئيسية
                - نقاط مهمة
                - خلاصة
                بدون تكرار
                """
            ])
            return {"summary": response.text}

        if not text.strip():
            raise HTTPException(status_code=400, detail="No text found")

        model = get_model()
        prompt = f"""
        أنت خبير تلخيص احترافي.

        لخص النص التالي بدون تكرار الأفكار:
        - دمج المتشابه
        - حذف الحشو
        - تنظيم منطقي
        - صياغة تعليمية واضحة

        الناتج:
        1. ملخص عام
        2. أفكار رئيسية
        3. نقاط تعليمية
        4. خلاصة نهائية

        النص:
        {text[:12000]}
        """

        response = model.generate_content(prompt)
        return {"summary": response.text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))