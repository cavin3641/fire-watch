# -*- coding: utf-8 -*-
"""
구글 뉴스 RSS 수집 - API 키가 필요 없습니다. 이 파일은 지금 바로 동작합니다.
"""
import urllib.parse
from datetime import datetime, timezone, timedelta

import feedparser

KST = timezone(timedelta(hours=9))
RSS_URL = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"


def fetch(keyword):
    """키워드로 뉴스를 검색해서 리스트로 돌려줍니다."""
    url = RSS_URL.format(q=urllib.parse.quote(f"{keyword} when:1d"))
    feed = feedparser.parse(url)

    results = []
    for entry in feed.entries:
        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(KST)

        results.append({
            "source": "구글뉴스",
            "title": entry.title,
            "url": entry.link,
            "published": published.isoformat() if published else None,
            "raw_text": entry.title,
        })
    return results
