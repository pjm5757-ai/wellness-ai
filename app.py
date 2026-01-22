import sqlite3
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

DB_PATH = "wellness.db"
load_dotenv()
client = OpenAI()  # OPENAI_API_KEY를 자동으로 읽음

# ---------- DB ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            sleep_hours REAL NOT NULL,
            stress INTEGER NOT NULL,
            mood INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_checkin(sleep_hours, stress, mood):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO daily_checkins (created_at, sleep_hours, stress, mood)
        VALUES (?, ?, ?, ?)
    """, (datetime.now().isoformat(timespec="seconds"), sleep_hours, stress, mood))
    conn.commit()
    conn.close()


def fetch_recent(limit=20):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, created_at, sleep_hours, stress, mood
        FROM daily_checkins
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def fetch_last_n(n=7):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT created_at, sleep_hours, stress, mood
        FROM daily_checkins
        ORDER BY id DESC
        LIMIT ?
    """, (n,))
    rows = cur.fetchall()
    conn.close()
    return list(reversed(rows))


# ---------- REPORT ----------
def make_weekly_report(rows):
    if len(rows) < 3:
        return "리포트를 만들 기록이 부족합니다. 최소 3번 이상 저장해 주세요."

    sleeps = [r[1] for r in rows]
    stress = [r[2] for r in rows]
    mood = [r[3] for r in rows]

    sleep_avg = round(sum(sleeps) / len(sleeps), 2)
    stress_avg = round(sum(stress) / len(stress), 2)
    mood_avg = round(sum(mood) / len(mood), 2)

    report = []
    report.append("[주간 리포트]")
    report.append(f"- 수면 평균: {sleep_avg} 시간")
    report.append(f"- 스트레스 평균: {stress_avg} /10")
    report.append(f"- 기분 평균: {mood_avg} /10")
    report.append("")

    if sleep_avg < 6:
        report.append("- 수면이 부족한 편입니다.")
    if stress_avg >= 7:
        report.append("- 스트레스가 높은 편입니다.")
    if mood_avg <= 4:
        report.append("- 기분이 낮은 편입니다.")

    report.append("")
    report.append("[추천]")
    report.append("- 취침 시간을 일정하게 유지하세요.")
    report.append("- 하루 10분 가볍게 걷기")
    report.append("- 오후 카페인 섭취 줄이기")

    return "\n".join(report)


# ---------- UI ----------
st.title("나의 스트레스 기분 측정기")

init_db()

sleep_hours = st.number_input("수면 시간 (시간)", 0.0, 24.0, 7.0, 0.5)
stress = st.slider("스트레스 (1~10)", 1, 10, 5)
mood = st.slider("기분 (1~10)", 1, 10, 6)

if st.button("저장하기"):
    save_checkin(float(sleep_hours), int(stress), int(mood))
    st.success("저장되었습니다.")

st.divider()
st.subheader("최근 기록")

rows = fetch_recent(10)
for r in rows:
    st.write(r)

st.divider()
st.subheader("주간 리포트")

last7 = fetch_last_n(7)
report = make_weekly_report(last7)

def ai_polish_report(raw_report: str) -> str:
    import os
    from openai import OpenAI

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return "오류: OPENAI_API_KEY를 못 읽었습니다. (.env 위치/내용 확인 후 재시작 필요)"

    try:
        client = OpenAI()  # 환경변수에서 키를 읽음

        prompt = f"""
너는 웰니스 코치다.
아래 '원본 리포트'의 숫자/사실/결론을 절대 바꾸지 말고,
문장만 더 자연스럽고 읽기 쉽게 다듬어라.

규칙:
- 의학적 진단/처방 금지
- 지표의 숫자와 의미를 바꾸지 말 것
- 출력은 한국어
- 너무 짧지 않게(최소 8~12문장), 하지만 900자 이내
- 구성: (1) 이번 주 요약 (2) 관찰 3가지 (3) 추천 3가지 (4) 다음 주 체크포인트 2가지
- 한국어, 친근한 톤

원본 리포트:
{raw_report}
""".strip()

        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
        text = resp.output_text.strip()
        if not text:
            return "오류: AI 응답이 비어 있습니다(Empty output)."
        return text

    except Exception as e:
        return f"AI 호출 오류: {type(e).__name__}: {e}"

if st.button("리포트 보기", key="weekly_report_btn"):
    last7 = fetch_last_n(7)
    report = make_weekly_report(last7)

    st.text("=== 원본 리포트 ===")
    st.text(report)

    st.text("=== 추천 체크포인트 ===")
    with st.spinner("AI가 문장을 다듬는 중..."):
        st.write(ai_polish_report(report))