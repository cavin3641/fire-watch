# -*- coding: utf-8 -*-
"""
행정안전부 긴급재난문자 API

[직접 하실 일]
1. safetydata.go.kr 회원가입 -> '행정안전부_긴급재난문자' 활용신청 (승인 1~3일)
2. 승인되면 서비스키를 .env 파일의 SAFETY_DATA_KEY 에 넣기
3. 아래 API_PATH 를 승인 페이지에 적힌 실제 경로로 맞추기
   (플랫폼 경로가 바뀔 수 있으니 반드시 신청 페이지에서 확인)
4. 응답 필드명(CRT_DT, MSG_CN 등)도 신청 페이지의 '출력결과' 표와 대조
"""
import requests

from config import SAFETY_DATA_KEY

BASE_URL = "https://www.safetydata.go.kr"
API_PATH = "/V2/api/DSSP-IF-00247"   # TODO: 신청 페이지에서 실제 경로 확인


def fetch(page_size=50):
    if not SAFETY_DATA_KEY:
        print("  [건너뜀] 재난문자: SAFETY_DATA_KEY 가 없습니다")
        return []

    params = {
        "serviceKey": SAFETY_DATA_KEY,   # K 는 반드시 대문자
        "returnType": "json",
        "pageNo": 1,
        "numOfRows": page_size,
    }

    try:
        res = requests.get(BASE_URL + API_PATH, params=params, timeout=10)
        res.raise_for_status()
        body = res.json().get("body", []) or []
    except Exception as e:
        print(f"  [실패] 재난문자 API: {e}")
        return []

    results = []
    for row in body:
        results.append({
            "source": "재난문자",
            "title": row.get("MSG_CN", ""),          # 문자 내용
            "url": "",
            "published": row.get("CRT_DT"),          # 발송 시각
            "region": row.get("RCPTN_RGN_NM", ""),   # 수신 지역
            "raw_text": row.get("MSG_CN", ""),
        })
    return results
