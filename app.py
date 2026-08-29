# -*- coding: utf-8 -*-
"""
서논술형 자동 채점 웹앱 (규칙 기반)
실행: streamlit run app.py
"""
import streamlit as st
from rubric_data import RUBRICS
from grading import evaluate_table, evaluate_essay_pair, evaluate_video

st.set_page_config(page_title="서논술형 자동 채점", layout="wide")

STATUS_COLOR = {"통과": "🟢", "부분점수": "🟡", "미흡": "🔴"}


def show_result_block(r):
    icon = STATUS_COLOR.get(r["status"], "")
    st.markdown(f"**{r['label']}** — {icon} {r['status']} ({r['score']}점)")
    for issue in r.get("issues", []):
        st.markdown(f"- ⚠️ {issue}")
    for note in r.get("notes", []):
        st.markdown(f"- ℹ️ {note}")
    if not r.get("issues") and not r.get("notes"):
        st.markdown("- ✅ 특이사항 없음")


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@700;900&family=Noto+Sans+KR:wght@400;500;700&display=swap');

    .grading-header-wrap {
        font-family: 'Noto Sans KR', sans-serif;
        padding: 22px 0 18px 0;
        border-bottom: 1px solid #E2E5EA;
        margin-bottom: 6px;
    }
    .grading-header-row {
        display: flex;
        align-items: center;
        gap: 18px;
        flex-wrap: wrap;
    }
    .grading-stamp {
        flex-shrink: 0;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        border: 3px solid #D6293E;
        color: #D6293E;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Noto Serif KR', serif;
        font-weight: 900;
        font-size: 14px;
        letter-spacing: -1px;
        transform: rotate(-9deg);
        line-height: 1.15;
        text-align: center;
        white-space: pre-line;
    }
    .grading-title-block {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: 10px;
    }
    .grading-title {
        font-family: 'Noto Serif KR', serif;
        font-weight: 900;
        font-size: 32px;
        color: #1B2A4A;
        letter-spacing: -0.5px;
        margin: 0;
    }
    .grading-tag {
        padding: 3px 10px;
        font-family: 'Noto Sans KR', sans-serif;
        font-size: 13px;
        font-weight: 700;
        color: #D6293E;
        border: 1.5px solid #D6293E;
        border-radius: 999px;
    }
    .grading-caption {
        margin-top: 12px;
        padding-left: 14px;
        border-left: 3px solid #D6293E;
        color: #5B6472;
        font-family: 'Noto Sans KR', sans-serif;
        font-size: 14.5px;
        line-height: 1.65;
        max-width: 760px;
    }
    @media (max-width: 640px) {
        .grading-title { font-size: 24px; }
        .grading-stamp { width: 46px; height: 46px; font-size: 11px; }
    }
    </style>

    <div class="grading-header-wrap">
        <div class="grading-header-row">
            <div class="grading-stamp">채점<br/>완료</div>
            <div class="grading-title-block">
                <span class="grading-title">서논술형 자동 채점</span>
                <span class="grading-tag">규칙 기반</span>
            </div>
        </div>
        <div class="grading-caption">
            키워드 그룹 매칭 · 오개념 트랩 · 결론 방향 확인을 기반으로 한 1차 자동 채점 도구입니다.<br/>
            자유서술형 텍스트 특성상 100% 정확하지 않을 수 있으므로, 결과는 반드시 교사가 최종 검수해 주세요.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

set_name = st.sidebar.radio("세트 선택", list(RUBRICS.keys()), format_func=lambda k: RUBRICS[k]["label"])
rubric = RUBRICS[set_name]
q_type = st.sidebar.radio("문항 선택", ["서논술형1 (표 완성)", "서논술형2 (이어지는 문장)", "서논술형3 (영상 기획안)"])
show_model = st.sidebar.checkbox("모범 답안 참고용으로 보기", value=False)

st.header(rubric["label"])

# ------------------------------------------------------------------
# 서논술형 1: 표 완성
# ------------------------------------------------------------------
if q_type.startswith("서논술형1"):
    st.subheader("서·논술형 1 — 표 완성 (㉠, ㉡, ㉢)")
    cols = st.columns(3)
    keys = list(rubric["table"].keys())
    answers = {}
    for i, key in enumerate(keys):
        with cols[i]:
            desc = rubric["table"][key].get("desc", "")
            answers[key] = st.text_area(f"{key} ({desc})", height=100, key=f"table_{set_name}_{key}")

    if show_model:
        with st.expander("모범 답안 보기"):
            for k in keys:
                st.markdown(f"**{k}**: {rubric['model_answers']['table'][k]}")

    if st.button("채점하기", key="grade_table"):
        result = evaluate_table(answers, rubric["table"])
        st.markdown("---")
        st.subheader(f"채점 결과 — 총점 {result['total_score']}점 (평균)")
        for key in keys:
            show_result_block(result["items"][key])
            st.markdown("")

# ------------------------------------------------------------------
# 서논술형 2: 이어지는 문장 (설명 방법 선택)
# ------------------------------------------------------------------
elif q_type.startswith("서논술형2"):
    st.subheader("서·논술형 2 — 이어지는 문장 (설명 방법 표기 포함)")
    st.caption("문장 끝에 사용한 설명 방법을 괄호로 표기해 주세요. 예: `...효과적이다.(예시)`")

    text1 = st.text_area("(1)", height=100, key=f"essay1_{set_name}")
    text2 = st.text_area("(2)", height=100, key=f"essay2_{set_name}")

    if show_model:
        with st.expander("선택지별 모범 답안 보기 (사용 가능한 설명 방법별 예시)"):
            for slot in ["1", "2"]:
                st.markdown(f"**({slot})번 문장 — 선택 가능한 설명 방법별 예시**")
                options = rubric["model_answers"]["essay"].get(slot, {})
                for method, sample in options.items():
                    st.markdown(f"- *{method}*: {sample}")

    if st.button("채점하기", key="grade_essay"):
        result = evaluate_essay_pair(text1, text2, rubric["essay"])
        st.markdown("---")
        st.subheader(f"채점 결과 — 총점 {result['total_score']}점 (평균)")
        st.markdown(f"- 감지된 설명 방법: (1) `{result['method1']}` / (2) `{result['method2']}`")
        if result["pair_issues"]:
            st.markdown("**공통(방법 선택) 관련 이슈**")
            for issue in result["pair_issues"]:
                st.markdown(f"- ⚠️ {issue}")
        show_result_block(result["r1"])
        show_result_block(result["r2"])

# ------------------------------------------------------------------
# 서논술형 3: 영상 기획안
# ------------------------------------------------------------------
else:
    st.subheader("서·논술형 3 — 영상 기획안 (장면 2)")
    colA, colB = st.columns(2)
    with colA:
        a_text = st.text_area("시각 요소(Ⓐ)", height=90, key=f"A_{set_name}")
        a_effect = st.text_area("시각 요소(Ⓐ)의 효과", height=90, key=f"Aeff_{set_name}")
    with colB:
        b_text = st.text_area("청각 요소(Ⓑ)", height=90, key=f"B_{set_name}")
        b_effect = st.text_area("청각 요소(Ⓑ)의 효과", height=90, key=f"Beff_{set_name}")

    if show_model:
        with st.expander("모범 답안 보기"):
            ma = rubric["model_answers"]["video"]
            st.markdown(f"**시각 요소(Ⓐ)**: {ma['A']}")
            st.markdown(f"**시각 요소 효과**: {ma['A_effect']}")
            st.markdown(f"**청각 요소(Ⓑ)**: {ma['B']}")
            st.markdown(f"**청각 요소 효과**: {ma['B_effect']}")

    if st.button("채점하기", key="grade_video"):
        answers = {"A": a_text, "A_effect": a_effect, "B": b_text, "B_effect": b_effect}
        result = evaluate_video(answers, rubric["video"])
        st.markdown("---")
        st.subheader(f"채점 결과 — 총점 {result['total_score']}점 (평균)")
        for key in ["A", "A_effect", "B", "B_effect"]:
            show_result_block(result["items"][key])
            st.markdown("")

st.markdown("---")
st.caption("⚙️ 채점 로직 요약: ① 조건에서 허용한 '의미'가 담기면 용어 없이도 인정 (필수 키워드 그룹 매칭) "
           "② 선택한 설명 방법의 특성 표현이 문장에 있는지 확인 ③ 반대/대구 개념 키워드 등장 시 오답 경고 "
           "④ 조건에서 요구한 결론 방향(긍정/부정)이 실제로 드러나는지 확인.")
