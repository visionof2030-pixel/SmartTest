<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>المنصة الذكية للاختبارات والتلخيص</title>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap" rel="stylesheet">
<style>
body{font-family:Tajawal;background:#0A3D62;color:white;padding:20px;margin:0}
.container{max-width:950px;margin:auto;background:#1A5F7A;padding:25px;border-radius:15px}
select,input,textarea,button{width:100%;padding:10px;margin:6px 0;border-radius:6px;border:none}
button{cursor:pointer;font-size:16px;background:#159895;color:white}
.option{border:1px solid #ccc;padding:12px;margin:8px 0;cursor:pointer;border-radius:6px}
.option.correct{background:#2e7d32}
.option.incorrect{background:#c62828}
.feedback{background:#0f766e;padding:10px;margin-top:5px;border-radius:6px;font-size:14px}
.hidden{display:none}
.tabs{display:flex;gap:10px;margin-bottom:15px}
.tabs button{flex:1}
.box{background:#0b2e4a;padding:20px;border-radius:10px;margin-top:15px;white-space:pre-wrap;line-height:1.8}
</style>
</head>

<body>

<div class="container">

<div class="tabs">
<button onclick="showTab('manual')">✍️ اختبار يدوي</button>
<button onclick="showTab('file')">📄 اختبار من ملف</button>
<button onclick="showTab('summary')">🧾 تلخيص ملف</button>
</div>

<!-- اختبار يدوي -->
<div id="manual">
<textarea id="topic" placeholder="اكتب موضوع الاختبار"></textarea>

<select id="manualCount">
<option value="5">5</option>
<option value="10" selected>10</option>
<option value="20">20</option>
<option value="30">30</option>
<option value="40">40</option>
<option value="50">50</option>
<option value="60">60</option>
</select>

<select id="lang">
<option value="ar">عربي</option>
<option value="en">English</option>
</select>

<button onclick="manualQuiz()">إنشاء الاختبار</button>
</div>

<!-- اختبار من ملف -->
<div id="file" class="hidden">
<input type="file" id="fileInput" accept=".pdf,.png,.jpg,.jpeg">

<select id="fileCount">
<option value="5">5</option>
<option value="10" selected>10</option>
<option value="20">20</option>
<option value="30">30</option>
<option value="40">40</option>
<option value="50">50</option>
<option value="60">60</option>
</select>

<select id="fileLang">
<option value="ar">عربي</option>
<option value="en">English</option>
</select>

<button onclick="fileQuiz()">إنشاء الأسئلة</button>
</div>

<!-- تلخيص -->
<div id="summary" class="hidden">
<input type="file" id="sumFile" accept=".pdf,.png,.jpg,.jpeg">
<select id="sumLang">
<option value="ar">عربي</option>
<option value="en">English</option>
</select>
<button onclick="summarize()">تلخيص الملف</button>
</div>

<div id="result"></div>
<button id="nextBtn" class="hidden" onclick="nextQuestion()">التالي</button>

</div>

<script>
const BACKEND="https://smarttest-0ycc.onrender.com"
let questions=[]
let answers=[]
let index=0

function showTab(t){
["manual","file","summary"].forEach(x=>document.getElementById(x).classList.add("hidden"))
document.getElementById(t).classList.remove("hidden")
result.innerHTML=""
nextBtn.classList.add("hidden")
}

function safeParse(t){
return JSON.parse(t.replace(/```json|```/g,"").trim())
}

async function manualQuiz(){
const count = manualCount.value

const prompt = `
أنشئ اختبار مكوّن من ${count} سؤال اختيار من متعدد حول الموضوع التالي:
${topic.value}

قواعد صارمة:
- 4 خيارات لكل سؤال
- شرح موسع للإجابة الصحيحة
- شرح مختصر لكل خيار خاطئ
- لا تكرر الأفكار
- لا تخرج عن الموضوع
- أعد النتيجة JSON فقط

الصيغة:
{
 "questions":[
  {
   "q":"",
   "options":["","","",""],
   "answer":0,
   "explanations":["","","",""]
  }
 ]
}
`

const r = await fetch(BACKEND+"/ask",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({prompt,language:lang.value})
})

const d = await r.json()
questions = safeParse(d.result).questions
answers = new Array(questions.length).fill(null)
index = 0
nextBtn.classList.remove("hidden")
renderQuestion()
}

async function fileQuiz(){
const fd=new FormData()
fd.append("file",fileInput.files[0])
fd.append("mode","questions")
fd.append("language",fileLang.value)
fd.append("num_questions", fileCount.value)

const r = await fetch(BACKEND+"/ask-file",{method:"POST",body:fd})
const d = await r.json()
questions = safeParse(d.result).questions
answers = new Array(questions.length).fill(null)
index = 0
nextBtn.classList.remove("hidden")
renderQuestion()
}

async function summarize(){
const fd=new FormData()
fd.append("file",sumFile.files[0])
fd.append("mode","summary")
fd.append("language",sumLang.value)

const r = await fetch(BACKEND+"/ask-file",{method:"POST",body:fd})
const d = await r.json()

result.innerHTML = `<div class="box">${d.result}</div>`
}

function renderQuestion(){
const q=questions[index]
let html=`<h3>${q.q}</h3>`

q.options.forEach((o,i)=>{
let cls="option"
if(answers[index]!==null){
if(i===q.answer) cls+=" correct"
else cls+=" incorrect"
}

html+=`
<div class="${cls}" onclick="choose(${i})">
${o}
${answers[index]!==null ? `<div class="feedback">${q.explanations[i]}</div>` : ""}
</div>`
})

result.innerHTML = html
}

function choose(i){
if(answers[index]!==null) return
answers[index]=i
renderQuestion()
}

function nextQuestion(){
if(index < questions.length-1){
index++
renderQuestion()
}else{
let correct=0
answers.forEach((a,i)=>{if(a===questions[i].answer) correct++})
result.innerHTML = `<h2>النتيجة: ${correct} / ${questions.length}</h2>`
nextBtn.classList.add("hidden")
}
}
</script>

</body>
</html>