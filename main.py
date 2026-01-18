from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import io
import pdfplumber
from PIL import Image
import base64

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
    model: str = "gemini-2.5-flash-lite"
    language: str = "ar"

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

def output_language(lang: str):
    if lang == "en":
        return "Write the final output in clear academic English."
    return "اكتب الناتج النهائي باللغة العربية الفصحى الواضحة."

def get_model():
    api_key = next(key_cycle)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash-lite")

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    try:
        model = get_model()
        lang_instruction = output_language(req.language)
        prompt = f"{lang_instruction}\n\n{req.prompt}"
        response = model.generate_content(prompt)
        return {"result": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_text_from_pdf(file_bytes: bytes):
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_text_from_image(file_bytes: bytes):
    image = Image.open(io.BytesIO(file_bytes))
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return buffered.getvalue()

@app.post("/ask-file")
async def ask_file(
    file: UploadFile = File(...),
    mode: str = Form("questions"),
    language: str = Form("ar"),
    num_questions: int = Form(10)
):
    try:
        file_bytes = await file.read()
        filename = file.filename.lower()

        if filename.endswith(".pdf"):
            text = extract_text_from_pdf(file_bytes)
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            image_bytes = extract_text_from_image(file_bytes)
            text = None
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        model = get_model()
        lang_instruction = output_language(language)

        if mode == "summary":
            prompt = f"""
You are a professional summarization expert.

Read the content regardless of its original language.

{lang_instruction}

Summarize with:
- No repetition
- Merge similar ideas
- Clear structure

Output:
1. General summary
2. Main ideas
3. Important points
4. Final conclusion

CONTENT:
{text[:12000] if text else ""}
"""
            if text:
                response = model.generate_content(prompt)
            else:
                response = model.generate_content([
                    prompt,
                    {
                        "mime_type": file.content_type,
                        "data": image_bytes
                    }
                ])
            return {"result": response.text}

        else:
            prompt = f"""
You are an expert educational content generator.

Read the content carefully regardless of its language.

{lang_instruction}

Create {num_questions} multiple choice questions.

Rules:
- 4 options
- Correct answer index
- Long explanation for correct answer
- Short explanation for wrong options

Return JSON ONLY:
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

CONTENT:
{text[:12000] if text else ""}
"""
            if text:
                response = model.generate_content(prompt)
            else:
                response = model.generate_content([
                    prompt,
                    {
                        "mime_type": file.content_type,
                        "data": image_bytes
                    }
                ])
            return {"result": response.text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))