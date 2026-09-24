# -*- coding: utf-8 -*-
"""
화재 기록 DB (월별 CSV)

docs/fires.json 은 지도용이라 48시간이 지나면 지웁니다.
여기는 지우지 않고 계속 쌓아서, 나중에 권역별·건물별 통계를 낼 수 있게 합니다.

  db/fires-2026-09.csv   ← 발생한 달 기준으로 한 파일
  엑셀에서 바로 열 수 있습니다 (한글 깨짐 방지 BOM 포함).

같은 화재는 한 줄입니다. 규모·신빙성·기사가 바뀌면 그 줄을 고쳐 씁니다.
※ 구글 뉴스 결과만 기록합니다. 네이버 검색 결과는 약관상 저장하지 않습니다.
"""
import csv
import os
from datetime import datetime, timezone, timedelta

import followup
import zones
from config import TELEGRAM_CHAT_ID

KST = timezone(timedelta(hours=9))
DB_DIR = "db"
MAX_ARTICLES = 5

COLUMNS = ["id", "발생시각", "처음확인", "마지막변경", "권역", "보낸곳", "출처",
           "지역", "건물", "건물종류", "화재종류", "진행상태", "등급",
           "신빙성", "규모", "규모근거", "관련기사수", "언론사", "관련기사"]


def _month_of(fire):
    for key in ("published", "first_seen"):
        t = followup._parse_time(fire.get(key))   # '2026/09/08 10:34:33' 형식도 읽습니다
        if t:
            return t.strftime("%Y-%m")
    return None


def _sent_to(fire):
    tg = fire.get("tg")
    if not tg:
        return ""
    return "사장님" if str(tg.get("chat")) == str(TELEGRAM_CHAT_ID) else "권역방"


def _row(fire):
    news = fire.get("news", [])
    presses = list(dict.fromkeys(n["press"] for n in news if n.get("press")))
    return {
        "id": fire.get("id", ""),
        "발생시각": fire.get("published") or "",
        "처음확인": fire.get("first_seen") or "",
        "권역": zones.zone_of(fire.get("region")),
        "보낸곳": _sent_to(fire),
        "출처": fire.get("source") or "",
        "지역": fire.get("region") or "",
        "건물": fire.get("building") or "",
        "건물종류": fire.get("bkind") or "",
        "화재종류": fire.get("kind") or "",
        "진행상태": fire.get("visit") or "",
        "등급": fire.get("grade") or "",
        "신빙성": fire.get("trust") or "",
        "규모": {"불명": "정보없음"}.get(fire.get("size"), fire.get("size") or ""),
        "규모근거": ", ".join(fire.get("size_why") or []),
        "관련기사수": str(len(news)),
        "언론사": ", ".join(presses),
        "관련기사": " | ".join(f"{n['title']} ({n['url']})" for n in news[:MAX_ARTICLES]),
    }


def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def save(fires):
    """이번 회차 목록을 월별 파일에 합쳐 씁니다."""
    now = datetime.now(KST).isoformat(timespec="seconds")
    by_month = {}
    for f in fires:
        m = _month_of(f)
        if m and f.get("id"):
            by_month.setdefault(m, []).append(f)

    os.makedirs(DB_DIR, exist_ok=True)
    total_new = total_changed = 0
    for month, items in by_month.items():
        path = os.path.join(DB_DIR, f"fires-{month}.csv")
        rows = _load(path)
        for f in items:
            new = _row(f)
            old = rows.get(new["id"])
            if old is None:
                total_new += 1
            elif all(old.get(k, "") == new[k] for k in new):
                continue                        # 바뀐 게 없으면 그대로 둡니다
            else:
                total_changed += 1
            new["마지막변경"] = now
            rows[new["id"]] = new

        ordered = sorted(rows.values(), key=lambda r: r.get("발생시각", ""))
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(ordered)

    print(f"[D] 기록 DB -> 새 {total_new}건, 갱신 {total_changed}건 ({DB_DIR}/)")
