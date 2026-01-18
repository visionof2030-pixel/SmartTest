from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import fitz
import docx
from PIL import Image
import pytesseract
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEYS = [
    os.getenv("GEMINI_KEY_1"),
    os.getenv("GEMINI_KEY_2"),
    os.getenv("GEMINI_KEY_3"),
    os.getenv("GEMINI_KEY_4"),
    os.getenv("GEMINI_KEY_5"),
    os.getenv("GEMINI_KEY_6"),
    os.getenv("GEMINI_KEY_7"),
]

API_KEYS = [k for k in API_KEYS if k]
key_cycle = itertools.cycle(API_KEYS)

def get_model():
    genai.configure(api_key=next(key_cycle))
    return genai.GenerativeModel("gemini-2.5-flash-lite")

def read_pdf(file_bytes):
    text = ""
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def read_docx(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)

def read_txt(file_bytes):
    return file_bytes.decode("utf-8", errors="ignore")

def read_image(file_bytes):
    img = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(img, lang="ara+eng")

class AskRequest(BaseModel):
    model: str
    prompt: str

@app.post("/ask")
async def ask(
    model: str = Form(None),
    prompt: str = Form(None),
    file: UploadFile = File(None),
    json: AskRequest = None
):
    final_prompt = ""

    if json:
        final_prompt = json.prompt

    if file:
        file_bytes = await file.read()
        ext = file.filename.lower()

        if ext.endswith(".pdf"):
            content = read_pdf(file_bytes)
        elif ext.endswith(".docx"):
            content = read_docx(file_bytes)
        elif ext.endswith(".txt"):
            content = read_txt(file_bytes)
        elif ext.endswith((".png", ".jpg", ".jpeg", ".webp")):
            content = read_image(file_bytes)
        else:
            content = ""

        final_prompt = f"""
المحتوى المستخرج من الملف:
{content}

المطلوب:
{prompt}
"""

    model_instance = get_model()
    result = model_instance.generate_content(final_prompt)

    return {"result": result.text}
