# -*- coding: utf-8 -*-
"""
네이버 검색 API (뉴스)

[직접 하실 일]
1. developers.naver.com -> 애플리케이션 등록 -> '검색' API 선택
2. Client ID / Secret 을 .env 에 넣기
3. 필요하면 아래 URL 을 blog.json / cafearticle.json 으로 바꿔 카페·블로그도 수집
"""
import requests

from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

URL = "https://openapi.naver.com/v1/search/news.json"


def fetch(keyword, display=30):
    if not NAVER_CLIENT_ID:
        print("  [건너뜀] 네이버: 키가 없습니다")
        return []

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": display, "sort": "date"}

    try:
        res = requests.get(URL, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        items = res.json().get("items", [])
    except Exception as e:
        print(f"  [실패] 네이버 API: {e}")
        return []

    results = []
    for it in items:
        title = it["title"].replace("<b>", "").replace("</b>", "")
        desc = it["description"].replace("<b>", "").replace("</b>", "")
        results.append({
            "source": "네이버뉴스",
            "title": title,
            "url": it.get("originallink") or it.get("link"),
            "published": it.get("pubDate"),
            "raw_text": f"{title} {desc}",
        })
    return results
