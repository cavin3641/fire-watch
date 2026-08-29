# -*- coding: utf-8 -*-
"""지역 언론사 RSS 수집 - 작은 화재는 지역신문에만 실립니다"""
from datetime import datetime, timezone, timedelta
import feedparser
KST = timezone(timedelta(hours=9))
FEEDS = [
    ("인천일보", "https://www.incheonilbo.com/rss/allArticle.xml"),
    ("중부일보", "https://www.joongboo.com/rss/allArticle.xml"),
    ("뉴시스", "https://www.newsis.com/RSS/sokbo.xml"),
]
def fetch():
    results = []
    for name, url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"  [실패] {name}: {type(e).__name__}")
            continue
        if not feed.entries:
            print(f"  [건너뜀] {name}")
            continue
        for entry in feed.entries:
            published = None
            if getattr(entry, "published_parsed", None):
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(KST)
            results.append({"source": name, "title": entry.title, "url": entry.link,
                "published": published.isoformat() if published else None,
                "raw_text": entry.title})
        print(f"  {name} {len(feed.entries)}건")
    return results
