# -*- coding: utf-8 -*-
"""우선순위 점수. 뉴스에 크게 난 현장은 경쟁자가 몰리므로 감점합니다."""
BUILDING_SCORE = {"고층건물": 35, "아파트": 35, "일반화재": 18}
DISPATCH_SCORE = {"3차출동": 35, "2차출동": 22, "1차출동": 0}
STATUS_SCORE = {"상황종료": 15, "귀소완료보고": 15, "귀소보고": 12, "초진": 5,
                "현장도착": 0, "현장도착보고": 0, "출동지령": -5, "추가출동지령": -5}
NEWS_PENALTY = -25
def score(fire):
    kind = fire.get("kind") or ""
    if "차량)" in kind:
        return 0
    pts = 5
    for key, val in BUILDING_SCORE.items():
        if key in kind:
            pts += val
            break
    scope = fire.get("scope") or ""
    for key, val in DISPATCH_SCORE.items():
        if key in scope:
            pts += val
            break
    pts += STATUS_SCORE.get(fire.get("status") or "", 0)
    if fire.get("in_news"):
        pts += NEWS_PENALTY
    dist = fire.get("distance_km")
    if isinstance(dist, (int, float)):
        if dist <= 15:
            pts += 12
        elif dist <= 30:
            pts += 6
        elif dist > 60:
            pts -= 10
    return max(0, min(100, pts))
def grade(pts):
    if pts >= 70:
        return "★★★"
    if pts >= 50:
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
