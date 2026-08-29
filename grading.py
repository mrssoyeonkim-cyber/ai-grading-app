# -*- coding: utf-8 -*-
"""채점 엔진: 규칙 기반(키워드+패턴) 자동 채점 로직."""
import re
from rubric_data import METHOD_PATTERNS, ALLOWED_METHODS, NEG_PARTICLES

STATUS_SCORE = {"통과": 100, "부분점수": 60, "미흡": 20}


def _matched_group(text, group):
    return any(kw in text for kw in group)


def _downgrade(status):
    order = ["통과", "부분점수", "미흡"]
    idx = order.index(status)
    return order[min(idx + 1, len(order) - 1)]


def _check_negation_near(text, keyword, window=12):
    """keyword 등장 위치 뒤 window자 이내에 부정 표현이 있는지 확인."""
    hits = []
    for m in re.finditer(re.escape(keyword), text):
        end = m.end()
        seg = text[end:end + window]
        if any(neg in seg for neg in NEG_PARTICLES):
            hits.append(keyword)
    return hits


def evaluate_blank(text, rubric, label=""):
    """단일 빈칸/문장에 대한 규칙 기반 평가."""
    text = (text or "").strip()
    issues = []
    notes = []

    if not text:
        return {"label": label, "status": "미흡", "score": 0, "issues": ["답안이 비어 있습니다."], "notes": []}

    # 0) 정확한 명칭이 필요한 경우 (허용 범위: 의미만으로는 불인정)
    if "exact_term" in rubric:
        term = rubric["exact_term"]
        if term not in text:
            issues.append(f"정확한 용어 '{term}'가 포함되어야 합니다. (의미만으로는 인정되지 않는 항목)")
            status = "미흡"
            for opp in rubric.get("opposite_keywords", []):
                if opp in text:
                    issues.append(f"반대/대구 개념 '{opp}'이(가) 감지되었습니다. 개념 혼동 가능성이 있습니다.")
            return {"label": label, "status": status, "score": STATUS_SCORE[status], "issues": issues, "notes": notes}
        else:
            status = "통과"

    else:
        # 1) 필수 키워드 그룹 체크 (그룹 내 하나라도 있으면 그 그룹 충족)
        required_groups = rubric.get("required_groups", [])
        min_groups = rubric.get("min_groups", len(required_groups))
        matched = [g for g in required_groups if _matched_group(text, g)]
        n_matched = len(matched)

        if required_groups:
            if n_matched >= min_groups and n_matched == len(required_groups):
                status = "통과"
            elif n_matched >= min_groups:
                status = "통과"  # 허용 범위상 min_groups 충족 시 통과, 나머지는 보너스
            elif n_matched > 0:
                status = "부분점수"
                missing = [g[0] for g in required_groups if g not in matched]
                issues.append(f"필수 내용 요소가 일부 부족합니다. (충족 {n_matched}/{len(required_groups)}) 추가로 필요: {', '.join(missing)} 등의 의미")
            else:
                status = "미흡"
                issues.append("필수 내용 요소가 답안에서 확인되지 않습니다.")
        else:
            status = "통과"

        # 2) 결론 요구(근거+결론이 모두 필요한 경우, 예: 세트3 ㉡)
        if "conclusion_required" in rubric:
            concl = rubric["conclusion_required"]
            if not any(kw in text for kw in concl):
                issues.append(f"요구된 결론 방향({'/'.join(concl)})이 답안에 명확히 드러나지 않습니다.")
                status = _downgrade(status) if status == "통과" else "미흡"

        # 3) 결론 방향 반전 감지 (negation_check)
        if "negation_check" in rubric:
            nc = rubric["negation_check"]
            for target in nc.get("target", []):
                if target in text:
                    # "예술이다"라는 표현이 부정 없이 그대로 있으면 결론이 반대로 서술된 것
                    if not _check_negation_near(text, target):
                        issues.append(f"'{target}'라는 표현이 부정 없이 사용되어 결론 방향이 지문과 반대로 서술된 것으로 보입니다.")
                        status = "미흡"

        # 4) 반대/대구 개념(개념 혼동) 체크
        for opp in rubric.get("opposite_keywords", []):
            if opp in text:
                issues.append(f"다른(반대) 개념의 표현 '{opp}'이(가) 감지되었습니다. 해당 개념의 특성을 잘못 가져온 것은 아닌지 확인이 필요합니다.")
                status = _downgrade(status)

        # 5) 흔한 오개념 표현 체크 (커스텀 메시지)
        for kw, msg in rubric.get("misconception_keywords", []):
            if kw in text:
                issues.append(f"[오개념 의심] {msg}")
                status = _downgrade(status)

        # 6) 근거 필수 여부 (requires_evidence=True면 그룹 미충족 시 바로 '미흡')
        if rubric.get("requires_evidence") and n_matched < len(required_groups) and status != "통과":
            status = "미흡"
            issues.append("이 항목은 '반드시 지문 근거 포함'이 조건이므로, 근거 표현이 부족하면 통과로 인정하지 않습니다.")

        # 7) 선택(optional) 그룹 -> 없으면 감점(다운그레이드 1단계) 안내만, fail 처리는 안 함
        for og in rubric.get("optional_groups", []):
            if not _matched_group(text, og):
                notes.append(f"보강 권장 표현 없음: {og[0]} 등 (없어도 '미흡' 처리는 아니지만 감점 요인)")

    return {"label": label, "status": status, "score": STATUS_SCORE[status], "issues": issues, "notes": notes}


def extract_method_label(text):
    m = re.search(r"\(([^()]+)\)\s*$", (text or "").strip())
    return m.group(1).strip() if m else None


def evaluate_essay_pair(text1, text2, essay_rubric):
    """서논술형2(이어지는 문장 두 개, 설명 방법 표기 포함) 평가."""
    results = {}
    method1 = extract_method_label(text1)
    method2 = extract_method_label(text2)
    pair_issues = []

    if not method1 or not method2:
        pair_issues.append("문장 끝 괄호에 사용한 설명 방법의 명칭이 표기되지 않았습니다.")
    if method1 and method1 not in ALLOWED_METHODS:
        pair_issues.append(f"(1) 표기한 방법 '{method1}'은(는) 인정되는 6가지 설명 방법 목록에 없습니다. ('비유'는 '비교와 대조'로 표기해야 함)")
    if method2 and method2 not in ALLOWED_METHODS:
        pair_issues.append(f"(2) 표기한 방법 '{method2}'은(는) 인정되는 6가지 설명 방법 목록에 없습니다. ('비유'는 '비교와 대조'로 표기해야 함)")
    if method1 and method2 and method1 == method2:
        pair_issues.append(f"(1)과 (2)에 동일한 설명 방법('{method1}')을 사용했습니다. 서로 다른 2가지 방법이어야 합니다.")

    # 방법의 '특성'이 문장에 실제로 드러나는지 확인
    for label, text, method in [("1", text1, method1), ("2", text2, method2)]:
        if method and method in METHOD_PATTERNS:
            patterns = METHOD_PATTERNS[method]
            if not any(p in (text or "") for p in patterns):
                pair_issues.append(f"({label}) 표기한 설명 방법 '{method}'의 특성(예: {', '.join(patterns[:3])} 등)이 문장에 드러나지 않습니다.")

    # 내용(개념) 평가
    r1 = evaluate_blank(text1, essay_rubric["answers"]["1"], label="(1)")
    r2 = evaluate_blank(text2, essay_rubric["answers"]["2"], label="(2)")

    # 결론 방향(전체적 가치 언급 등) 체크 - 세트3에서 사용
    ovc = essay_rubric.get("overall_value_check")
    if ovc:
        combined = f"{text1} {text2}"
        has_value = any(k in combined for k in ovc["keywords"])
        has_neg = any(k in combined for k in ovc["avoid_keywords"])
        if not has_value or has_neg:
            pair_issues.append(f"[결론 방향] {ovc['message']}")

    # 방법-혼동 이슈가 있으면 다운그레이드
    def apply_pair_penalty(r, n_pair_issues):
        if n_pair_issues == 0:
            return r
        r = dict(r)
        r["status"] = _downgrade(r["status"])
        r["score"] = STATUS_SCORE[r["status"]]
        return r

    n_issue_for_penalty = 1 if pair_issues else 0
    r1 = apply_pair_penalty(r1, n_issue_for_penalty)
    r2 = apply_pair_penalty(r2, n_issue_for_penalty)

    results["method1"] = method1
    results["method2"] = method2
    results["pair_issues"] = pair_issues
    results["r1"] = r1
    results["r2"] = r2
    results["total_score"] = round((r1["score"] + r2["score"]) / 2)
    return results


def evaluate_table(answers_dict, table_rubric):
    """서논술형1(표 완성) 평가. answers_dict: {"㉠": text, ...}"""
    results = {}
    for key, rubric in table_rubric.items():
        results[key] = evaluate_blank(answers_dict.get(key, ""), rubric, label=key)
    total = round(sum(r["score"] for r in results.values()) / len(results)) if results else 0
    return {"items": results, "total_score": total}


def evaluate_video(answers_dict, video_rubric):
    """서논술형3(영상 기획안) 평가. answers_dict: {"A":..,"A_effect":..,"B":..,"B_effect":..}"""
    results = {}
    for key, rubric in video_rubric.items():
        label_map = {"A": "시각 요소(Ⓐ)", "A_effect": "시각 요소 효과", "B": "청각 요소(Ⓑ)", "B_effect": "청각 요소 효과"}
        results[key] = evaluate_blank(answers_dict.get(key, ""), rubric, label=label_map.get(key, key))
    total = round(sum(r["score"] for r in results.values()) / len(results)) if results else 0
    return {"items": results, "total_score": total}
