# -*- coding: utf-8 -*-
"""우선순위 점수. 뉴스에 크게 난 현장은 경쟁자가 몰리므로 감점합니다."""
# 대형화재(시장,공장)가 복구 규모가 가장 큽니다
BUILDING_SCORE = {"대형화재": 45, "고층건물": 38, "아파트": 38, "일반화재": 20}

# 시설 종류가 없는 '기타화재'는 건물인지 불확실하므로 낮게
OTHER_FIRE_SCORE = 8
# 출동 차수는 시도마다 표기 관행이 다릅니다.
# 서울은 거의 모두 '2차출동', 경기·인천은 거의 모두 '1차출동'으로 적습니다.
# 그대로 점수에 쓰면 서울 건만 위로 올라오므로,
# '그 지역에서 흔한 표기인지'를 보고 판단합니다.
DISPATCH_SCORE = {"3차출동": 35, "2차출동": 22, "1차출동": 0}

# 지역별로 '2차출동' 표기가 얼마나 흔한지 (수집 때마다 다시 계산)
_scope_common = {}


def learn_scope_pattern(fires):
    """지역별 출동차수 표기 관행을 파악합니다.

    어떤 시도에서 2차출동이 절반을 넘으면 그건 '큰 불'이 아니라
    그냥 그 지역의 기본 표기입니다. 그럴 땐 가산점을 주지 않습니다.
    """
    _scope_common.clear()
    tally = {}
    for f in fires:
        if f.get("source") != "소방출동":
            continue
        sido = (f.get("region") or "").split()[0] if f.get("region") else ""
        if not sido:
            continue
        t = tally.setdefault(sido, [0, 0])
        t[0] += 1
        if "2차" in (f.get("scope") or "") or "3차" in (f.get("scope") or ""):
            t[1] += 1
    for sido, (total, high) in tally.items():
        # 절반 넘게 2차출동이면 = 그 지역 기본 표기 = 변별력 없음
        _scope_common[sido] = (total >= 5 and high / total > 0.5)
    return _scope_common
STATUS_SCORE = {"상황종료": 15, "귀소완료보고": 15, "귀소보고": 12, "초진": 5,
                "현장도착": 0, "현장도착보고": 0, "출동지령": -5, "추가출동지령": -5}
NEWS_PENALTY = -25

# 거리 가산점 사용 여부.
# 지역별로 담당자를 두면 사무실 거리는 의미가 없으므로 False 로 둡니다.
# (경기도는 넓어서 평균 39km, 서울은 20km라 서울만 유리해집니다)
USE_DISTANCE_BONUS = False
def score(fire):
    kind = fire.get("kind") or ""
    if "차량)" in kind:
        return 0
    pts = 5
    for key, val in BUILDING_SCORE.items():
        if key in kind:
            pts += val
            break
    # 그 지역에서 2차출동이 기본 표기면 가산점을 주지 않습니다
    sido = (fire.get("region") or "").split()[0] if fire.get("region") else ""
    if not _scope_common.get(sido, False):
        scope = fire.get("scope") or ""
        for key, val in DISPATCH_SCORE.items():
            if key in scope:
                pts += val
                break
    pts += STATUS_SCORE.get(fire.get("status") or "", 0)
    if fire.get("in_news"):
        pts += NEWS_PENALTY
    # 기타화재는 건물 여부가 불확실합니다
    if "기타" in kind:
        pts += OTHER_FIRE_SCORE

    # 최근 화재일수록 먼저 갑니다 (오래된 건은 이미 다른 업체가 다녀갔을 확률)
    pub = fire.get("published") or ""
    if pub:
        try:
            from datetime import datetime, timezone, timedelta
            KST = timezone(timedelta(hours=9))
            hours = (datetime.now(KST) - datetime.fromisoformat(pub)).total_seconds() / 3600
            if hours <= 12:
                pts += 18
            elif hours <= 24:
                pts += 12
            elif hours <= 48:
                pts += 5
            else:
                pts -= 8
        except Exception:
            pass

    dist = fire.get("distance_km") if USE_DISTANCE_BONUS else None
    if isinstance(dist, (int, float)):
        if dist <= 15:
            pts += 12
        elif dist <= 30:
            pts += 6
        elif dist > 60:
            pts -= 10
    return max(0, min(100, pts))
def grade(pts):
    if pts >= 58:
        return "★★★"
    if pts >= 45:
        return "★★"
    if pts >= 30:
        return "★"
    return ""
def mark_news_overlap(fires):
    """같은 시군구에 뉴스가 있으면 표시합니다 (경쟁자도 아는 건)"""
    news = [f for f in fires if f.get("source") != "소방출동"]
    for d in [f for f in fires if f.get("source") == "소방출동"]:
        d_area = " ".join((d.get("region") or "").split()[:2])
        for n in news:
            if d_area and d_area == " ".join((n.get("region") or "").split()[:2]):
                d["in_news"] = True
                d["news_url"] = n.get("url")
                break
    return fires
