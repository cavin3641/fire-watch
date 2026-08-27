# -*- coding: utf-8 -*-
"""
지역명(주소) -> 위도/경도 변환

[직접 하실 일]
1. developers.kakao.com -> 앱 등록 -> REST API 키 발급
2. .env 의 KAKAO_REST_KEY 에 넣기
"""
import math

import requests

from config import KAKAO_REST_KEY, BASE_LAT, BASE_LON

ADDR_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
_cache = {}   # 같은 지역을 여러 번 물어보지 않게 저장해 둡니다


def to_coords(region_name):
    """지역명을 (위도, 경도)로 바꿉니다. 실패하면 None."""
    if not region_name or not KAKAO_REST_KEY:
        return None
    if region_name in _cache:
        return _cache[region_name]

    headers = {"Authorization": f"KakaoAK {KAKAO_REST_KEY}"}
    docs = []

    # 1차: 주소 검색 (정확하지만 까다로움)
    # 2차: 키워드 검색 (관대함 - "울산 무거동" 같은 것도 찾아줍니다)
    for url in (ADDR_URL, KEYWORD_URL):
        try:
            res = requests.get(url, headers=headers,
                               params={"query": region_name}, timeout=10)
            res.raise_for_status()
            docs = res.json().get("documents", [])
        except Exception as e:
            print(f"  [실패] 좌표 변환 '{region_name}': {e}")
            return None
        if docs:
            break

    if not docs:
        return None

    coords = (float(docs[0]["y"]), float(docs[0]["x"]))
    _cache[region_name] = coords
    return coords


def distance_km(lat, lon):
    """우리 사무실에서 얼마나 떨어져 있는지 계산합니다."""
    r = 6371
    d_lat = math.radians(lat - BASE_LAT)
    d_lon = math.radians(lon - BASE_LON)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(BASE_LAT)) * math.cos(math.radians(lat))
         * math.sin(d_lon / 2) ** 2)
    return round(r * 2 * math.asin(math.sqrt(a)), 1)
