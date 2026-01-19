from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
import os
import itertools
import math

app = FastAPI()

class AskRequest(BaseModel):
    prompt: str
    language: str = "ar"
    total_questions: int = 10

class FileQuizRequest(BaseModel):
    content: str
    language: str = "ar"
    total_questions: int = 10

class SummaryRequest(BaseModel):
    content: str
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

MODEL_NAME = "models/gemini-2.5-flash-lite"
MAX_PER_BATCH = 10
MAX_TOTAL = 60

def call_gemini(prompt: str):
    api_key = next(key_cycle)
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text

def generate_batches(base_prompt: str, total: int):
    total = min(total, MAX_TOTAL)
    batches = math.ceil(total / MAX_PER_BATCH)
    results = []

    for i in range(batches):
        count = min(MAX_PER_BATCH, total - len(results))
        prompt = base_prompt.replace("{N}", str(count))
        text = call_gemini(prompt)
        results.append(text)

    return "\n".join(results)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/ask")
def manual_quiz(req: AskRequest):
    base_prompt = f"""
أنشئ {{N}} سؤال اختبار حول الموضوع التالي:

{req.prompt}

اللغة المطلوبة: {req.language}

الشروط:
- كل سؤال يحتوي على 4 خيارات
- لكل خيار شرح مختصر
- شرح الإجابة الصحيحة يكون موسع وتعليمي
- أعد النتيجة بصيغة JSON فقط بهذا الشكل:

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
    result = generate_batches(base_prompt, req.total_questions)
    return {"result": result}

@app.post("/quiz-from-file")
def quiz_from_file(req: FileQuizRequest):
    base_prompt = f"""
اعتماداً على المحتوى التالي:

{req.content}

أنشئ {{N}} سؤال اختبار.

اللغة المطلوبة: {req.language}

الشروط:
- كل سؤال يحتوي على 4 خيارات
- لكل خيار شرح مختصر
- شرح الإجابة الصحيحة يكون موسع
- أعد النتيجة بصيغة JSON فقط بنفس الهيكل التالي:

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
    result = generate_batches(base_prompt, req.total_questions)
    return {"result": result}

@app.post("/summarize")
def summarize(req: SummaryRequest):
    prompt = f"""
لخص المحتوى التالي بأسلوب احترافي تعليمي.

اللغة المطلوبة: {req.language}

قواعد:
- لا تكرر الأفكار
- استخدم عناوين فرعية
- ركز على الفهم وليس النسخ
- إذا كان المحتوى كبيراً، اختصره بذكاء

المحتوى:
{req.content}
"""
    result = call_gemini(prompt)
    return {"result": result}