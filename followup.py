# -*- coding: utf-8 -*-
"""
화재 규모 추적 (후속 확인)

소방청에서 주소를 받은 뒤 6시간 동안, 매 회차(30분)마다
구글 뉴스에서 그 동네·건물 기사를 찾아 제목의 단어로 규모를 판정합니다.

  🟢 대형 / 🔴 소형 / 🟡 불명

등급이 바뀌면 처음 보낸 알림에 '답장' 형태로 다시 알립니다.

※ 판정은 구글 뉴스 제목으로만 합니다.
※ 네이버 기사는 판정에 쓰지 않고, 링크만 붙여서 보여줍니다 (약관).
"""
import re
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
from datetime import datetime, timezone, timedelta

import feedparser

import naver_links
import notify

KST = timezone(timedelta(hours=9))
RSS_URL = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"

FOLLOW_HOURS = 6                          # 발생 후 몇 시간 동안 추적할지
TRACK_SOURCES = ("소방출동", "재난문자")    # 주소가 확실한 출처만 추적

# 다음 회차로 넘겨야 하는 값들 (collect.py 가 덮어써도 살려둡니다)
KEEP_KEYS = ("size", "size_why", "size_news", "tg")

LABEL = {"대형": "🟢 대형", "소형": "🔴 소형", "불명": "🟡 불명"}
RANK = {"불명": 0, "소형": 1, "대형": 2}

# ── 판정 단어 ─────────────────────────────────────────────
# 여기 단어만 고치면 판정 기준이 바뀝니다.
BIG_WORDS = [
    "전소", "대응 1단계", "대응1단계", "대응 2단계", "대응2단계", "대응단계",
    "연소 확대", "번져", "옮겨붙", "큰불", "대형 화재", "대형화재",
    "헬기", "숨져", "사망", "잿더미", "모두 타", "건물 전체",
]
SMALL_WORDS = [
    "초기 진화", "초기진화", "자체 진화", "자체진화", "조기 진화",
    "소화기로", "일부 소실", "부분 소실", "일부 태워", "일부를 태워",
    "경미", "연기만", "주방 일부", "베란다 일부",
]
# 숫자가 들어간 표현: (패턴, 기준값) — 기준값 이상이면 대형
BIG_NUMBERS = [
    (r"(\d+)\s*개\s*층", 2),          # 2개 층 이상
    (r"(\d+)\s*여?\s*명\s*(?:이\s*)?(?:긴급\s*)?(?:대피|구조)", 10),  # 10명(10여 명) 이상 대피
    (r"(?:소방차|장비)\s*(\d+)\s*대", 20),
    (r"(\d+)\s*여?\s*명\s*(?:부상|다쳐|중상|경상)", 3),
    (r"(\d+)\s*억", 1),               # 재산피해 1억 이상
    (r"(\d+)\s*시간\s*만에\s*(?:큰\s*)?(?:불길|완진|진화|꺼져)", 2),
]
# 이 숫자 이하면 소형 (예: 10분 만에 진화)
SMALL_NUMBERS = [
    (r"(\d+)\s*분\s*만에\s*(?:큰\s*)?(?:불길|완진|진화|꺼져)", 30),
]


# ── 시간 계산 ─────────────────────────────────────────────
def _parse_time(s):
    if not s:
        return None
    for fmt in (None, "%Y/%m/%d %H:%M:%S"):
        try:
            t = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            return t if t.tzinfo else t.replace(tzinfo=KST)
        except ValueError:
            continue
    return None


def _in_window(fire, now):
    t = _parse_time(fire.get("published"))
    return t is not None and now - t <= timedelta(hours=FOLLOW_HOURS)


# ── 검색어 만들기 ─────────────────────────────────────────
def _names(fire):
    """기사 제목에서 찾을 이름들: 동 이름, 건물 이름."""
    parts = (fire.get("region") or "").split()
    dong = parts[-1] if len(parts) >= 3 else ""
    dong = re.sub(r"\d+가$", "", dong)             # 회현동1가 → 회현동
    city = parts[1] if len(parts) >= 2 else ""
    city = re.sub(r"(특별시|광역시|시|군|구)$", "", city)

    bld = (fire.get("building") or "").split()
    bld = bld[0] if bld else ""                    # '라온힐요양병원 라온힐요양병원' → 앞 단어
    # '수서6단지아파트' → '수서6단지' (기사에는 '수서6단지 아파트'로 띄어 씀)
    bld = re.sub(r"(아파트|오피스텔|빌딩|빌라|주택|상가|건물)$", "", bld)
    if len(bld) < 3:
        bld = ""
    return city, dong, bld


def _queries(fire):
    city, dong, bld = _names(fire)
    qs = []
    if bld:
        qs.append(f'"{bld}" 화재')
    if dong:
        qs.append(f"{city} {dong} 화재".strip())
    return qs


# ── 뉴스 찾기 (구글) ──────────────────────────────────────
def _google_titles(query, since):
    url = RSS_URL.format(q=urllib.parse.quote(f"{query} when:1d"))
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"  [실패] 구글 뉴스: {e}")
        return []
    out = []
    for e in feed.entries:
        if getattr(e, "published_parsed", None):
            t = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).astimezone(KST)
            if t < since:
                continue                           # 화재 이전 기사(옛날 사건) 제외
        out.append(e.title)
    return out


def _related(title, fire):
    """이 기사가 정말 그 화재 얘기인지: 동/건물 이름 + 불 관련 단어."""
    _, dong, bld = _names(fire)
    if not any(w in title for w in ("화재", "불", "연기")):
        return False
    flat = title.replace(" ", "")                  # 띄어쓰기 차이 무시
    return bool((dong and dong in flat) or (bld and bld.replace(" ", "") in flat))


# ── 규모 판정 ─────────────────────────────────────────────
def judge(titles):
    """기사 제목들을 보고 (규모, 근거단어들) 을 돌려줍니다."""
    big, small = [], []
    for t in titles:
        for w in BIG_WORDS:
            if w in t:
                big.append(w)
        for w in SMALL_WORDS:
            if w in t:
                small.append(w)
        for pat, limit in BIG_NUMBERS:
            for m in re.finditer(pat, t):
                if int(m.group(1)) >= limit:
                    big.append(m.group(0))
        for pat, limit in SMALL_NUMBERS:
            for m in re.finditer(pat, t):
                if int(m.group(1)) <= limit:
                    small.append(m.group(0))

    big, small = list(dict.fromkeys(big)), list(dict.fromkeys(small))
    if big:                       # 대형 단서가 하나라도 있으면 대형 우선
        return "대형", big[:4]
    if small:
        return "소형", small[:4]
    return "불명", []


# ── 이전 회차 값 살리기 ───────────────────────────────────
def carry_over(previous, current):
    """collect.py 가 새 결과로 덮어쓰기 전에, 추적용 값을 옮겨 둡니다."""
    old = {f.get("id"): f for f in previous}
    for f in current:
        p = old.get(f.get("id"))
        if p:
            for k in KEEP_KEYS:
                if k in p and k not in f:
                    f[k] = p[k]


# ── 메인 ─────────────────────────────────────────────────
def run(fires):
    """fires: 저장 직전의 전체 목록. 규모를 갱신하고, 바뀐 건은 재발송."""
    now = datetime.now(KST)
    targets = [f for f in fires
               if f.get("source") in TRACK_SOURCES and _in_window(f, now)]
    print(f"[F] 규모 추적 대상 {len(targets)}건 (발생 {FOLLOW_HOURS}시간 이내)")

    # 대상별 기사 검색을 동시에 진행 (실행 시간 단축)
    def gather(f):
        since = _parse_time(f.get("published")) - timedelta(minutes=30)
        titles = []
        for q in _queries(f):
            titles += [t for t in _google_titles(q, since) if _related(t, f)]
        # 언론사만 다른 같은 기사 합침
        return list(dict.fromkeys(t.rsplit(" - ", 1)[0] for t in titles))

    with ThreadPoolExecutor(max_workers=6) as pool:
        all_titles = list(pool.map(gather, targets))

    changed = 0
    for f, titles in zip(targets, all_titles):
        new_size, why = judge(titles)
        old_size = f.get("size", "불명")

        # 한 번 올라간 등급은 내리지 않습니다 (기사마다 표현이 달라 오락가락 방지)
        if RANK[new_size] <= RANK[old_size]:
            f.setdefault("size", old_size)
            continue

        f["size"], f["size_why"], f["size_news"] = new_size, why, len(titles)
        changed += 1
        print(f"    -> {f.get('region')} : {old_size} → {new_size} {why}")
        notify.send_update(f, _update_text(f, old_size))

    print(f"    -> 등급 변경 {changed}건 재발송")


def _update_text(f, old_size):
    lines = [
        f"🔄 규모 업데이트: {LABEL[old_size]} → {LABEL[f['size']]}",
        f"📍 {f.get('region') or ''} {f.get('building') or ''}".strip(),
    ]
    if f.get("size_why"):
        lines.append(f"근거: {', '.join(f['size_why'])} (기사 {f.get('size_news', 0)}건)")

    # 네이버 기사: 판정에 쓰지 않고 제목·링크만 그대로 보여줍니다.
    city, dong, bld = _names(f)
    q = f"{bld} 화재" if bld else f"{city} {dong} 화재"
    links = naver_links.search(q.strip(), n=3)
    if links:
        lines.append("")
        lines.append("📰 관련 기사")
        for title, url in links:
            lines.append(f"· {title}\n  {url}")
    return "\n".join(lines)
