# AI აგენტების შექმნა და მართვა .NET-ში — ლექციები

STEP-ის AI მოდულის (24 ლექცია) ყველა ლექცია ერთ ადგილას: პრეზენტაცია, კონსპექტი, კლასის და საშინაო დავალება, მასალები.

**სტეკი:** .NET 10 · Microsoft.Extensions.AI · Microsoft Agent Framework · MCP · PostgreSQL + pgvector · EF Core 10
**პროექტი:** RestaurantApi (API კურსიდან) — მენიუ, კალათა, შეკვეთა, ჯავშანი; ყოველ ლექციაზე ემატება AI.

## ლექციაზე

1. გახსენი საიტი, შეიყვანე კოდი (ერთხელ), აირჩიე ლექცია → **▶ პრეზენტაცია**.
2. გადაიტანე პროექტორზე, დააჭირე `F`.
3. `P` — **კონსპექტი** ცალკე ფანჯარაში. ის სლაიდებს მიჰყვება; კონსპექტში „სლაიდი N“-ზე დაჭერა პრეზენტაციას იმ სლაიდზე გადაიყვანს.
4. ნავიგაცია ისრებით: `→` შემდეგი, `←` წინა.

სხვა კლავიშები: `O` ყველა სლაიდი · `A` სლაიდის ყველა ნაბიჯი · `Shift+→` შემდეგი სლაიდი. ასოები ქართულ განლაგებაზეც მუშაობს.

სტუდენტები კონსპექტს და მასალებს სახლში ქარდიდან ხსნიან: **📖 კონსპექტი**, 📎 მასალები.

## სტრუქტურა

```
engine/                      ძრავი: engine.js · engine.css · theme-light.css · index.html · study.html · gate.html
courses/ai/
  course.json                {"title", "order"}
  <NN-slug>/
    deck.html                სლაიდები; ყოველ სლაიდში — <aside class="study"> (სტუდენტის ახსნა, markdown)
    lecture.json             {"title", "why", "outcomes", "review"}
    classwork.md             კლასში დავალება
    homework.md              საშინაო (+ ამოხსნა, რომელიც მხოლოდ შემდეგ ლექციაზე ჩანს)
    materials/               ფაილები ჩამოსატვირთად (ცხრილები, SQL, კოდი…)
build.py                     აწყობს საიტს
```

| # | ლექცია | საქაღალდე |
|---|---|---|
| 01 | შესავალი Generative AI-სა და LLM API-ებში | `courses/ai/01-genai-llm-intro/` |

## ლექციის სტრუქტურა

ყველა ნაწილი სავალდებულოა — `deck.html`-ში ცხადი tag-ებით, რომლებსაც build სლაიდებად აქცევს:

| tag | სლაიდი | საიდან |
|---|---|---|
| `<lecture-review/>` | გამეორება — წინა ლექციის კითხვები | წინა ლექციის `lecture.json` → `review` |
| `<lecture-homework-review/>` | წინა საშინაოს განხილვა + ამოხსნა | წინა ლექციის `homework.md` |
| `<lecture-intro/>` | დღის თემა: რატომ გჭირდებათ, რას შეძლებთ | `lecture.json` → `why`, `outcomes` |
| `<lecture-classwork/>` | კლასში დავალება | `classwork.md` |
| `<lecture-check/>` | შევამოწმოთ — ამ ლექციის კითხვები | `lecture.json` → `review` |
| `<lecture-homework/>` | საშინაო (ამოხსნის გარეშე) | `homework.md` |

ერთი და იგივე კითხვები ლექციის ბოლოს „შევამოწმოთ“-ში ჩანს და შემდეგი ლექციის დასაწყისში „გამეორებაში“ — ერთხელ იწერება. build შეჩერდება, თუ ლექციას რომელიმე ნაწილი აკლია.

`classwork.md` / `homework.md`: `# სათაური`, ქვესათაური, მერე `## მოთხოვნები` (ან `## ნაბიჯები`), `## ✓ მზადაა, როცა`, `## ⭐ ბონუსი`, `## 💡 …` (მხოლოდ კონსპექტში), `## ამოხსნა` (მხოლოდ homework-ში; ჩანს შემდეგ ლექციაზე; სლაიდზე გამოსაჩენი კოდის ბლოკი მონიშნე სათაურის ბოლოს `!`-ით).

## კონსპექტის ფორმატი

`<aside class="study">` — ჩვეულებრივი markdown (სათაურები, სიები, ცხრილები). სლაიდი ტექსტის გარეშე წინა ბლოკს უერთდება. დამატებითი ბლოკები:

````
```csharp Controllers/AiLabController.cs     ← კოდი, სათაურით და „კოპირება“ ღილაკით
```prompt AI-სთვის                            ← პრომპტი ChatGPT/Claude/Gemini-სთვის, კოპირდება
```check                                      ← „შეამოწმე თავი“: ? კითხვა / = პასუხი
```terms                                      ← ტერმინები: ტერმინი — ახსნა
```note · ```warn · ```tip                    ← გამოყოფილი შენიშვნა
````

## ახალი ლექცია

1. `courses/ai/<NN-slug>/` — `deck.html`, `lecture.json`, `classwork.md`, `homework.md` (+ `materials/`).
2. ზემოთ ცხრილში დაამატე ხაზი.
3. ლოკალურად შეამოწმე (`build.py ai/NN`), შემდეგ commit + push `main`-ზე — Vercel თავისით ააწყობს.

## კოდი

საიტი კოდით იხსნება: ყველა HTML გვერდი ბილდისას იშიფრება (AES-GCM, გასაღები კოდიდან). ერთხელ შეყვანილ კოდს ბრაუზერი იმახსოვრებს.

- კოდი: გარემოს ცვლადი **`LECTURES_CODE`** (Vercel-ზე — Project Settings → Environment Variables). ლოკალურად — ან ცვლადი, ან `.access-code` ფაილი (ერთი ხაზი, git-ში არ შედის).
- კოდის შესაცვლელად — შეცვალე ცვლადი და Redeploy. ძველი კოდი აღარ იმუშავებს.

## Vercel

`vercel.json` მზადაა: Vercel აყენებს `requirements.txt`-ს, უშვებს `LECTURES_OUT=dist python3 build.py`-ს და აქვეყნებს **მხოლოდ** `dist/`-ს (`courses/`, `build.py` საიტზე არ ხვდება).

1. vercel.com → Add New → Project → `ai-learnigy/lectures`.
2. Environment Variables: `LECTURES_CODE` = კოდი.
3. Deploy.

## ლოკალურად

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # ერთხელ
.venv/bin/python build.py              # ყველაფერი → root (git-ში არ შედის)
.venv/bin/python build.py ai/01        # მხოლოდ ერთი ლექცია
python3 -m http.server 8000            # http://localhost:8000
```
