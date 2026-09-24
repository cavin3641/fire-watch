# -*- coding: utf-8 -*-
"""
네이버 뉴스·블로그·카페 링크 (API HUB)

우리가 수집한 주소(동·건물 이름)로 검색해서
그 주소가 제목에 들어 있고 화재 이후에 올라온 글만 골라 알림에 붙입니다.

약관(2026.9.7 개정)에 맞춰
- 규모 판정 등 분석에는 쓰지 않습니다 (판정은 구글 뉴스로만)
- 제목·링크를 고치지 않고 그대로 보여줍니다
- 내용은 기록(DB)에 저장하지 않습니다 (몇 건 찾았는지만 셉니다)
"""
import html
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import requests

from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

KST = timezone(timedelta(hours=9))
BASE = "https://naverapihub.apigw.ntruss.com/search/v1/"
KINDS = {"뉴스": "news", "블로그": "blog", "카페": "cafearticle"}


def _clean(s):
    """<b> 태그와 &quot; 같은 기호만 화면용으로 정리 (내용은 그대로)"""
    return html.unescape(re.sub(r"</?b>", "", s or ""))


def _posted(item):
    """글이 올라온 시각. 뉴스는 pubDate, 블로그는 postdate(날짜만), 카페는 없음."""
    try:
        if item.get("pubDate"):
            return parsedate_to_datetime(item["pubDate"]).astimezone(KST)
        if item.get("postdate"):
            return datetime.strptime(item["postdate"], "%Y%m%d").replace(tzinfo=KST)
    except (TypeError, ValueError):
        pass
    return None


def search(query, kind="뉴스", n=10):
    """[{title, url, posted}, ...] 를 돌려줍니다. 실패하면 빈 목록."""
    if not NAVER_CLIENT_ID:
        return []
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": n, "sort": "date"}
    try:
        res = requests.get(BASE + KINDS[kind], headers=headers, params=params, timeout=10)
        res.raise_for_status()
        items = res.json().get("items", [])
    except Exception as e:
        print(f"  [실패] 네이버 {kind}: {e}")
        return []
    return [{"title": _clean(it.get("title")),
             "url": it.get("link") or it.get("originallink"),
             "posted": _posted(it)} for it in items]


def matching(query, is_about, since):
    """뉴스·블로그·카페에서 그 주소 얘기이고 화재 이후에 올라온 글만.

    is_about(title) : 제목에 동·건물 이름과 불 관련 단어가 있는지
    since           : 화재 발생 시각 (블로그는 날짜 단위라 그날 0시부터)
    돌려주는 값     : {"뉴스": [...], "블로그": [...], "카페": [...]}
    """
    out = {}
    for kind in KINDS:
        day0 = since.replace(hour=0, minute=0, second=0, microsecond=0)
        limit = day0 if kind == "블로그" else since
        out[kind] = [it for it in search(query, kind)
                     if is_about(it["title"])
                     and (it["posted"] is None or it["posted"] >= limit)]
    return out
