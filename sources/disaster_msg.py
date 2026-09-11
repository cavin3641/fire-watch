# -*- coding: utf-8 -*-
"""행정안전부 긴급재난문자 API"""
from datetime import datetime, timezone, timedelta

import requests
from config import SAFETY_DATA_KEY
KST = timezone(timedelta(hours=9))

URL = "https://www.safetydata.go.kr/V2/api/DSSP-IF-00247"
def _to_iso(s):
    """재난문자는 '2026/09/08 10:34:33' 형식으로 옵니다.
    다른 데이터와 맞추려면 '2026-09-08T10:34:33+09:00' 로 바꿔야 합니다.
    이걸 안 하면 날짜 계산이 실패해서 점수와 삭제가 제대로 안 됩니다."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=KST).isoformat()
        except ValueError:
            continue
    return None


def fetch(page_size=100):
    if not SAFETY_DATA_KEY:
        print("  [건너뜀] 재난문자 키 없음")
        return []
    params = {"serviceKey": SAFETY_DATA_KEY, "returnType": "json", "pageNo": 1, "numOfRows": page_size}
    data = None
    for attempt in range(3):
        try:
            res = requests.get(URL, params=params, timeout=40)
            res.raise_for_status()
            data = res.json()
            break
        except Exception as e:
            print(f"  [재시도 {attempt + 1}] {type(e).__name__}")
    if data is None:
        print("  [실패] 재난문자 접속 불가")
        return []
    print(f"  [진단] {data.get('header')}")
    body = data.get("body") or []
    if isinstance(body, dict):
        body = body.get("items") or []
    print(f"  [진단] 건수 {len(body)}")
    if body:
        print(f"  [진단] 필드 {list(body[0].keys())}")
    results = []
    for row in body:
        text = row.get("MSG_CN") or row.get("msgCn") or ""
        results.append({"source": "재난문자", "title": text, "url": "", "raw_text": text,
            "published": _to_iso(row.get("CRT_DT") or row.get("crtDt")),
            "region": row.get("RCPTN_RGN_NM") or row.get("rcptnRgnNm") or ""})
    return results
