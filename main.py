from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import google.generativeai as genai
import os
import itertools
import math
import json
import re

app = FastAPI()

class AskRequest(BaseModel):
    prompt: str = Field(..., min_length=3)
    language: str = Field(default="ar")
    total_questions: int = Field(default=10, ge=5, le=60)

class FileQuizRequest(BaseModel):
    content: str = Field(..., min_length=20)
    language: str = Field(default="ar")
    total_questions: int = Field(default=10, ge=5, le=60)

class SummaryRequest(BaseModel):
    content: str = Field(..., min_length=20)
    language: str = Field(default="ar")

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

MODEL_NAME = "models/gemini-2.5-flash-lite"
MAX_PER_BATCH = 10
MAX_TOTAL = 60

def call_gemini(prompt: str) -> str:
    last_error = None
    for _ in range(len(keys)):
        try:
            api_key = next(key_cycle)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = str(e)
            continue
    raise RuntimeError(f"All keys failed: {last_error}")

def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError("JSON not found in model response")
        return json.loads(match.group())

def generate_questions(base_prompt: str, total: int) -> dict:
    total = min(total, MAX_TOTAL)
    batches = math.ceil(total / MAX_PER_BATCH)
    all_questions = []

    for _ in range(batches):
        count = min(MAX_PER_BATCH, total - len(all_questions))
        prompt = base_prompt.replace("{N}", str(count))
        text = call_gemini(prompt)
        data = extract_json(text)

        if "questions" not in data or not isinstance(data["questions"], list):
            raise ValueError("Invalid questions format from model")

        all_questions.extend(data["questions"])

    return {"questions": all_questions[:total]}

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def manual_quiz(req: AskRequest):
    base_prompt = f"""
أنشئ {{N}} سؤال اختبار حول الموضوع التالي:

{req.prompt}

اللغة المطلوبة: {req.language}

قواعد صارمة:
- أسئلة اختيار من متعدد
- 4 خيارات لكل سؤال
- لكل خيار تغذية راجعة توضح لماذا هو صحيح أو خاطئ
- شرح موسع وتعليمي للإجابة الصحيحة فقط
- لا تكتب أي نص خارج JSON

الصيغة المطلوبة (JSON فقط):

{{
  "questions": [
    {{
      "question": "...",
      "options": [
        {{"text": "...", "feedback": "..."}},
        {{"text": "...", "feedback": "..."}},
        {{"text": "...", "feedback": "..."}},
        {{"text": "...", "feedback": "..."}}
      ],
      "correct": 0,
      "correct_feedback": "شرح موسع وعميق للإجابة الصحيحة"
    }}
  ]
}}
"""
    try:
        return generate_questions(base_prompt, req.total_questions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/quiz-from-file")
def quiz_from_file(req: FileQuizRequest):
    base_prompt = f"""
اعتماداً على المحتوى التالي:

{req.content}

أنشئ {{N}} سؤال اختبار.

اللغة المطلوبة: {req.language}

قواعد صارمة:
- أسئلة اختيار من متعدد
- 4 خيارات لكل سؤال
- لكل خيار تغذية راجعة
- شرح موسع للإجابة الصحيحة
- لا تكتب أي نص خارج JSON

الصيغة المطلوبة (JSON فقط):

{{
  "questions": [
    {{
      "question": "...",
      "options": [
        {{"text": "...", "feedback": "..."}},
        {{"text": "...", "feedback": "..."}},
        {{"text": "...", "feedback": "..."}},
        {{"text": "...", "feedback": "..."}}
      ],
      "correct": 0,
      "correct_feedback": "شرح موسع للإجابة الصحيحة"
    }}
  ]
}}
"""
    try:
        return generate_questions(base_prompt, req.total_questions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarize")
def summarize(req: SummaryRequest):
    prompt = f"""
لخص المحتوى التالي بأسلوب احترافي وتعليمي.

اللغة المطلوبة: {req.language}

قواعد:
- لا تكرر الأفكار
- استخدم عناوين فرعية واضحة
- ركز على الفهم العميق
- مناسب للطلاب

المحتوى:
{req.content}
"""
    try:
        summary = call_gemini(prompt)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))