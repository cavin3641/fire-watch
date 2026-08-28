# -*- coding: utf-8 -*-
"""행정안전부 긴급재난문자 API (승인 URL: /V2/api/DSSP-IF-00247)"""
import requests
from config import SAFETY_DATA_KEY
BASE_URL = "https://www.safetydata.go.kr"
API_PATH = "/V2/api/DSSP-IF-00247"
def fetch(page_size=100):
    if not SAFETY_DATA_KEY:
        print("  [건너뜀] 재난문자: SAFETY_DATA_KEY 가 없습니다")
        return []
    params = {
        "serviceKey": SAFETY_DATA_KEY,
        "returnType": "json",
        "pageNo": 1,
        "numOfRows": page_size,
    }
      data = None
    for attempt in range(3):
        try:
            res = requests.get(BASE_URL + API_PATH, params=params, timeout=40)
            res.raise_for_status()
            data = res.json()
            break
        except Exception as e:
            print(f"  [재시도 {attempt + 1}/3] 재난문자: {type(e).__name__}")
    if data is None:
        print("  [실패] 재난문자 API 접속 불가")
        return []
      print(f"  [진단] header: {data.get('header')}")
    print(f"  [진단] 응답 키: {list(data.keys())}")
    body = data.get("body") or []
    if isinstance(body, dict):
        body = body.get("items") or []
    print(f"  [진단] 건수 {len(body)}")
    if body:
        print(f"  [진단] 필드명 {list(body[0].keys())}")
    results = []
    for row in body:
        text = row.get("MSG_CN") or row.get("msgCn") or ""
        results.append({
            "source": "재난문자",
            "title": text,
            "url": "",
            "published": row.get("CRT_DT") or row.get("crtDt"),
            "region": row.get("RCPTN_RGN_NM") or row.get("rcptnRgnNm") or "",
            "raw_text": text,
        })
    return results
