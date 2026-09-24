# -*- coding: utf-8 -*-
"""
네이버 뉴스 링크 (API HUB)

약관상 네이버 검색 결과는 AI 입력·가공이 금지되어 있으므로
판정에는 절대 쓰지 않고, 기사 제목과 링크를 '보여주기'만 합니다.
"""
import html
import re

import requests

from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"


def search(query, n=3):
    """[(제목, 링크), ...] 를 돌려줍니다. 실패하면 빈 목록."""
    if not NAVER_CLIENT_ID:
        return []
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": n, "sort": "date"}
    try:
        res = requests.get(URL, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        items = res.json().get("items", [])
    except Exception as e:
        print(f"  [실패] 네이버 HUB: {e}")
        return []

    out = []
    for it in items[:n]:
        # <b> 태그와 &quot; 같은 기호만 화면용으로 정리 (내용은 그대로)
        title = html.unescape(re.sub(r"</?b>", "", it.get("title", "")))
        out.append((title, it.get("link") or it.get("originallink")))
    return out
