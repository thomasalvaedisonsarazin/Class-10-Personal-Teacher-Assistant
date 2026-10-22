"""Printable HTML for model papers and their answer keys (the app prints it to PDF).

Everything from the paper is escaped. Labels follow the paper's language (en / ta).
"""

from __future__ import annotations

from html import escape
from typing import Any

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "class": "Class {grade}",
        "paper": "Model Question Paper",
        "key": "Answer Key and Suggested Answers",
        "full": "Full syllabus",
        "unit": "Unit test",
        "time": "Time",
        "marks": "Maximum marks",
        "name": "Name",
        "date": "Date",
        "part": "PART – {label}",
        "all": "Answer all the questions.",
        "mcq": "Choose the correct answer and write the option with the answer.",
        "any": "Answer any {n} questions.",
        "compulsory": "Question No. {n} is compulsory.",
        "either": "Answer either (a) or (b) in each question.",
        "or": "(OR)",
        "letters": "abcd",
        "hours": "{h} hours",
        "hour": "1 hour",
        "minutes": "{m} minutes",
        "instructions": "Instructions",
        "i1": "Read every question carefully. Use blue or black ink.",
        "i2": "Write the question number clearly before each answer.",
        "i3": "When you finish, take clear photos of every answer page, in order, and upload "
        "them in the app to get your marks and the answer key.",
        "answer": "Answer",
        "marking": "Marking points",
        "your_marks": "Your marks",
        "not_attempted": "Not attempted",
        "chosen": "you answered ({choice})",
        "scored": "Marks scored",
        "feedback": "Examiner's feedback",
        "chapters": "Chapters",
    },
    "ta": {
        "class": "வகுப்பு {grade}",
        "paper": "மாதிரி வினாத்தாள்",
        "key": "விடைக் குறிப்பு மற்றும் மாதிரி விடைகள்",
        "full": "முழுப் பாடத்திட்டம்",
        "unit": "அலகுத் தேர்வு",
        "time": "நேரம்",
        "marks": "மொத்த மதிப்பெண்கள்",
        "name": "பெயர்",
        "date": "தேதி",
        "part": "பகுதி – {label}",
        "all": "அனைத்து வினாக்களுக்கும் விடையளிக்கவும்.",
        "mcq": "சரியான விடையைத் தேர்ந்தெடுத்துக் குறியீட்டுடன் எழுதவும்.",
        "any": "ஏதேனும் {n} வினாக்களுக்கு விடையளிக்கவும்.",
        "compulsory": "வினா எண் {n} கட்டாய வினா.",
        "either": "ஒவ்வொரு வினாவிலும் (அ) அல்லது (ஆ) ஏதேனும் ஒன்றுக்கு விடையளிக்கவும்.",
        "or": "(அல்லது)",
        "letters": "அஆஇஈ",
        "hours": "{h} மணி நேரம்",
        "hour": "1 மணி நேரம்",
        "minutes": "{m} நிமிடம்",
        "instructions": "அறிவுரைகள்",
        "i1": "ஒவ்வொரு வினாவையும் கவனமாகப் படிக்கவும். நீலம் அல்லது கருப்பு மையைப் பயன்படுத்தவும்.",
        "i2": "ஒவ்வொரு விடைக்கும் முன் வினா எண்ணைத் தெளிவாக எழுதவும்.",
        "i3": "எழுதி முடித்ததும், எல்லா விடைத்தாள் பக்கங்களையும் வரிசையாகத் தெளிவாகப் புகைப்படம் "
        "எடுத்து ஆப்பில் பதிவேற்றவும்; மதிப்பெண்களும் விடைக் குறிப்பும் கிடைக்கும்.",
        "answer": "விடை",
        "marking": "மதிப்பீட்டுக் குறிப்புகள்",
        "your_marks": "உங்கள் மதிப்பெண்",
        "not_attempted": "எழுதவில்லை",
        "chosen": "நீங்கள் எழுதியது ({choice})",
        "scored": "பெற்ற மதிப்பெண்கள்",
        "feedback": "தேர்வாளரின் கருத்து",
        "chapters": "பாடங்கள்",
    },
}

CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'Noto Sans Tamil', 'Noto Sans', 'Nirmala UI', Arial, sans-serif; color: #111;
  font-size: 12.5pt; line-height: 1.45; margin: 0; }
header { text-align: center; border-bottom: 2px solid #111; padding-bottom: 8px;
  margin-bottom: 10px; }
h1 { font-size: 15pt; margin: 0; } h2 { font-size: 14pt; margin: 4px 0; }
h3 { font-size: 13pt; margin: 2px 0; }
.meta { display: flex; justify-content: space-between; font-weight: 700; margin-top: 8px; }
.blank { display: flex; gap: 24px; margin: 10px 0; }
.blank span { flex: 1; border-bottom: 1px solid #555; }
.small { font-size: 10.5pt; color: #333; }
.part { margin-top: 16px; page-break-inside: auto; }
.part-head { display: flex; justify-content: space-between; font-weight: 700;
  border-top: 1px solid #999; border-bottom: 1px solid #999; padding: 4px 0; text-align: center; }
.note { font-style: italic; margin: 4px 0 8px; }
.q { display: flex; gap: 8px; margin: 8px 0; page-break-inside: avoid; }
.q .n { min-width: 34px; font-weight: 700; }
.q .t { flex: 1; white-space: pre-wrap; }
.opts { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 16px; margin-top: 4px; }
.or { text-align: center; font-weight: 700; margin: 4px 0; }
.key { margin: 4px 0 10px 42px; padding: 6px 10px; border-left: 3px solid #4a7;
  background: #f4f8f4; }
.key .lbl { font-weight: 700; }
.got { font-weight: 700; color: #164; } .miss { font-weight: 700; color: #a33; }
table { border-collapse: collapse; margin: 8px auto; }
td, th { border: 1px solid #999; padding: 4px 10px; }
"""


def _labels(language: str) -> dict[str, str]:
    return LABELS.get(language, LABELS["en"])


def _duration(minutes: int, lab: dict[str, str]) -> str:
    hours, rest = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(lab["hour"] if hours == 1 else lab["hours"].format(h=hours))
    if rest:
        parts.append(lab["minutes"].format(m=rest))
    return " ".join(parts)


def _marks_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _header(paper: dict[str, Any], title_key: str, lab: dict[str, str]) -> str:
    head = paper["header"]
    scope = lab["full"] if head["scope"] == "full" else lab["unit"]
    chapters = ""
    if head["scope"] == "chapters" and head.get("chapters"):
        chapters = (
            f'<div class="small">{escape(lab["chapters"])}: '
            f"{escape(', '.join(head['chapters']))}</div>"
        )
    return (
        f"<header><h1>{escape(head['board'])}</h1>"
        f"<h2>{escape(lab['class'].format(grade=head['grade']))} — {escape(head['subject'])}</h2>"
        f"<h3>{escape(lab[title_key])} ({escape(scope)})</h3>{chapters}"
        f'<div class="meta"><span>{escape(lab["time"])}: '
        f"{escape(_duration(head['duration_minutes'], lab))}</span>"
        f"<span>{escape(lab['marks'])}: {head['total_marks']}</span></div></header>"
    )


def _part_note(part: dict[str, Any], lab: dict[str, str]) -> str:
    notes: list[str] = []
    if part["answer"] < part["printed"]:
        notes.append(lab["any"].format(n=part["answer"]))
    else:
        notes.append(lab["all"])
    if part["kind"] == "mcq":
        notes.append(lab["mcq"])
    if part["either_or"]:
        notes.append(lab["either"])
    compulsory = [q["number"] for q in part["questions"] if q.get("compulsory")]
    if compulsory:
        notes.append(lab["compulsory"].format(n=compulsory[0]))
    return " ".join(notes)


def _option_lines(options: list[str], lab: dict[str, str]) -> str:
    letters = lab["letters"]
    cells = "".join(
        f"<div>({letters[i] if i < len(letters) else i + 1}) {escape(o)}</div>"
        for i, o in enumerate(options)
    )
    return f'<div class="opts">{cells}</div>'


def _question(q: dict[str, Any], lab: dict[str, str]) -> str:
    body = escape(q["text"])
    if q.get("options"):
        body += _option_lines(q["options"], lab)
    html = f'<div class="q"><div class="n">{q["number"]}.</div><div class="t">'
    if q.get("alt_text"):
        a, b = lab["letters"][0], lab["letters"][1]
        html += (
            f'({a}) {body}<div class="or">{escape(lab["or"])}</div>({b}) {escape(q["alt_text"])}'
        )
    else:
        html += body
    return html + "</div></div>"


def _document(title: str, body: str) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"
    )


def paper_html(paper: dict[str, Any], language: str) -> str:
    """The question paper the student prints or writes from (no answers)."""
    lab = _labels(language)
    body = [_header(paper, "paper", lab)]
    body.append(
        f'<div class="blank"><div>{escape(lab["name"])}:</div><span></span>'
        f"<div>{escape(lab['date'])}:</div><span></span></div>"
        f'<div class="small"><b>{escape(lab["instructions"])}:</b> 1. {escape(lab["i1"])} '
        f"2. {escape(lab['i2'])} 3. {escape(lab['i3'])}</div>"
    )
    for part in paper["parts"]:
        total = part["answer"] * part["marks"]
        body.append(
            f'<section class="part"><div class="part-head"><span></span>'
            f"<span>{escape(lab['part'].format(label=part['label']))}</span>"
            f"<span>{part['answer']} × {part['marks']} = {total}</span></div>"
            f'<div class="note">{escape(_part_note(part, lab))}</div>'
            + "".join(_question(q, lab) for q in part["questions"])
            + "</section>"
        )
    return _document(f"{paper['header']['subject']} — {lab['paper']}", "".join(body))


def _key_block(
    answer: str, points: list[str], lab: dict[str, str], options: list[str] | None = None
) -> str:
    shown = answer
    if options and answer in options:
        index = options.index(answer)
        letters = lab["letters"]
        shown = f"({letters[index] if index < len(letters) else index + 1}) {answer}"
    html = f'<div><span class="lbl">{escape(lab["answer"])}:</span> {escape(shown)}</div>'
    if points:
        items = "".join(f"<li>{escape(p)}</li>" for p in points)
        html += f'<div class="lbl">{escape(lab["marking"])}:</div><ul>{items}</ul>'
    return html


def key_html(
    paper: dict[str, Any],
    answer_key: dict[str, Any],
    results: dict[str, Any] | None,
    language: str,
) -> str:
    """Answer key with suggested answers (and the student's marks once marked)."""
    lab = _labels(language)
    keys: dict[str, Any] = answer_key.get("answers", {})
    marked: dict[str, Any] = (results or {}).get("questions", {})
    body = [_header(paper, "key", lab)]
    if results:
        rows = "".join(
            f"<tr><td>{escape(lab['part'].format(label=p['label']))}</td>"
            f"<td>{_marks_text(p['scored'])} / {p['total']}</td></tr>"
            for p in results.get("parts", [])
        )
        body.append(
            f"<table><tr><th>{escape(lab['scored'])}</th>"
            f"<th>{_marks_text(results.get('score', 0))} / "
            f"{paper['header']['total_marks']}</th></tr>"
            f"{rows}</table>"
        )
        if results.get("feedback"):
            body.append(f"<p><b>{escape(lab['feedback'])}:</b> {escape(results['feedback'])}</p>")
    for part in paper["parts"]:
        body.append(
            f'<section class="part"><div class="part-head"><span></span>'
            f"<span>{escape(lab['part'].format(label=part['label']))}</span><span></span></div>"
        )
        for q in part["questions"]:
            key = keys.get(str(q["number"]), {})
            body.append(_question(q, lab))
            block = ""
            if q.get("alt_text"):
                a, b = lab["letters"][0], lab["letters"][1]
                block += f"<div><b>({a})</b></div>" + _key_block(
                    key.get("answer", ""), key.get("points", []), lab
                )
                block += f"<div><b>({b})</b></div>" + _key_block(
                    key.get("alt_answer") or "", key.get("alt_points", []), lab
                )
            else:
                block += _key_block(
                    key.get("answer", ""), key.get("points", []), lab, q.get("options")
                )
            mark = marked.get(str(q["number"]))
            if mark is not None:
                if mark.get("attempted"):
                    choice = mark.get("choice") or ""
                    letter = lab["letters"][0 if choice == "a" else 1]
                    chosen = f" — {escape(lab['chosen'].format(choice=letter))}" if choice else ""
                    block += (
                        f'<div class="got">{escape(lab["your_marks"])}: '
                        f"{_marks_text(mark.get('marks', 0))} / {part['marks']}{chosen}</div>"
                    )
                    if mark.get("feedback"):
                        block += f"<div>{escape(mark['feedback'])}</div>"
                else:
                    block += f'<div class="miss">{escape(lab["not_attempted"])}</div>'
            body.append(f'<div class="key">{block}</div>')
        body.append("</section>")
    return _document(f"{paper['header']['subject']} — {lab['key']}", "".join(body))
