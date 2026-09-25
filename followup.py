# -*- coding: utf-8 -*-
"""
화재 규모·신빙성 추적 (후속 확인)

알림을 보낸 뒤 24시간 동안, 매 회차(30분)마다
구글 뉴스에서 그 동네·건물 기사를 찾아

  규모   : 🔴 대형 / 🟢 소형 / 🟡 정보없음   (제목의 단어로 판정)
  신빙성 : 공식 기록(소방청·재난문자)인지, 언론 몇 곳이 보도했는지
  진화   : 초진 / 완진 (완진이면 방문 가능)
  층     : 몇 층 건물의 몇 층에서 났는지
  물 피해: 아래층 물 피해 보도 또는 가능성 (누수복구 영업용)

를 정합니다. 같은 주소로 네이버 뉴스·블로그도 찾아서
그 주소 얘기이고 화재 이후에 올라온 글을 모아 둡니다.

규모가 올라가거나 새 기사·글이 나오면
처음 보낸 알림에 '답장' 형태로 다시 알립니다.
결과는 db.py 가 월별 기록 파일(db/)에 계속 쌓습니다.

※ 규모 판정은 구글 뉴스 + 네이버 '뉴스' 제목으로 합니다.
  (AI 없이 정해 둔 단어가 있는지만 봅니다. 블로그는 판정에 안 씀)
※ 네이버 글은 제목·링크를 고치지 않고 그대로 알림에 보여주고,
  기록(DB)에는 내용 없이 찾은 건수만 남깁니다.
"""
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
from datetime import datetime, timezone, timedelta

import feedparser

import naver_links
import notify

KST = timezone(timedelta(hours=9))
RSS_URL = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"

FOLLOW_HOURS = 24                         # 발생 후 몇 시간 동안 추적할지
OFFICIAL = ("소방출동", "재난문자")         # 공식 기록으로 보는 출처
MAX_NEWS = 8                              # 한 건당 기억해 둘 관련 기사 수

# 다음 회차로 넘겨야 하는 값들 (collect.py 가 덮어써도 살려둡니다)
KEEP_KEYS = ("size", "size_why", "size_news", "tg", "news", "trust",
             "naver_seen", "naver_count",
             "out", "floor", "floor_top", "water", "water_why")

LABEL = {"대형": "🔴 대형", "소형": "🟢 소형", "불명": "🟡 정보없음"}
RANK = {"불명": 0, "소형": 1, "대형": 2}
TRUST_LABEL = {"공식+보도": "✅ 공식 기록 + 언론 보도",
               "공식": "✅ 공식 기록 (보도 없음)",
               "보도": "📰 언론 여러 곳 보도",
               "미확인": "⚠️ 기사 1곳뿐 · 확인 필요"}

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
def _google_news(query, since):
    """[{title, press, url}, ...]  구글 제목은 '기사 제목 - 언론사' 형식입니다."""
    url = RSS_URL.format(q=urllib.parse.quote(f"{query} when:2d"))   # 화재 이전 기사는 아래에서 거름
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
        title, _, press = e.title.rpartition(" - ")
        if not title:
            title, press = e.title, ""
        out.append({"title": title, "press": press, "url": e.link})
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


# ── 영업용 추가 판정 (진화 상태 · 발화 층 · 아래층 물 피해) ──────
# 진화 상태: 단계가 높을수록 불이 더 꺼진 것
OUT_WORDS = {
    "완진": ["완진", "완전 진화", "완전진화", "진화 완료", "진화완료",
             "모두 꺼", "불 꺼져", "진화됐", "진화돼", "진화했"],
    "초진": ["초진", "큰 불길 잡", "큰불 잡", "불길 잡혀", "불길 잡아"],
}
OUT_RANK = {"": 0, "초진": 1, "완진": 2}
OUT_LABEL = {"초진": "🧯 초진 (큰 불길 잡힘)", "완진": "✅ 완진 (불 다 꺼짐) → 방문 가능"}

# 발화 층: '7층에서', '7층 베란다' 등 / 건물 높이: '15층 아파트', '15층짜리'
FLOOR_FIRE = r"(\d{1,2})\s*층\s*(?:에서|서|의|베란다|주방|거실|안방|세대|집|집에서)"
FLOOR_TOP = r"(\d{1,2})\s*층\s*(?:짜리\s*)?(?:아파트|건물|빌라|오피스텔|주상복합|상가)"

# 아래층 물 피해: 기사에 직접 나온 경우
WATER_WORDS = ["아래층", "아랫층", "아랫집", "아래 세대", "아래세대", "침수",
               "물바다", "누수", "물 피해", "물피해", "수손", "물이 새", "물 새"]
MULTI_UNIT = ("아파트", "빌라", "오피스텔", "주상복합", "다세대", "연립")


def _out_status(titles):
    best = ""
    for t in titles:
        for status, words in OUT_WORDS.items():
            if OUT_RANK[status] > OUT_RANK[best] and any(w in t for w in words):
                best = status
    return best


def _floors(titles):
    """(발화 층, 건물 층수). 모르면 0."""
    fire_fl = top = 0
    for t in titles:
        for m in re.finditer(FLOOR_TOP, t):
            top = max(top, int(m.group(1)))
        for m in re.finditer(FLOOR_FIRE, t):
            fire_fl = fire_fl or int(m.group(1))
    if top and fire_fl > top:          # '15층 아파트 20층에서' 같은 오인 방지
        fire_fl = 0
    return fire_fl, top


def _water(fire, titles, fire_fl):
    """아래층 물 피해: ('보도', 근거) / ('가능', 근거) / ('', '')."""
    words = [w for w in WATER_WORDS if any(w in t for t in titles)]
    if words:
        return "보도", ", ".join(words[:3])
    multi = (fire.get("bkind") == "아파트" or fire.get("bkind") == "주택·빌라"
             or any(w in (fire.get("building") or "") for w in MULTI_UNIT)
             or any(w in t for t in titles for w in MULTI_UNIT))
    if multi and fire_fl >= 2:
        return "가능", f"{fire_fl}층 발화"
    return "", ""


def extra_checks(fire, titles):
    """진화 상태·층·물 피해를 갱신하고, 새로 알게 된 게 있으면 True."""
    changed = False

    out = _out_status(titles)
    if OUT_RANK[out] > OUT_RANK[fire.get("out", "")]:
        fire["out"] = out
        changed = True

    fire_fl, top = _floors(titles)
    if fire_fl and not fire.get("floor"):
        fire["floor"] = fire_fl
        changed = True
    if top and not fire.get("floor_top"):
        fire["floor_top"] = top
        changed = True

    water, why = _water(fire, titles, fire.get("floor", 0))
    old = fire.get("water", "")
    if water and (not old or (old == "가능" and water == "보도")):
        fire["water"], fire["water_why"] = water, why
        changed = True
    return changed


def floor_text(fire):
    if fire.get("floor") and fire.get("floor_top"):
        return f"{fire['floor_top']}층 건물 중 {fire['floor']}층"
    if fire.get("floor"):
        return f"{fire['floor']}층"
    if fire.get("floor_top"):
        return f"{fire['floor_top']}층 건물 (발화 층 모름)"
    return ""


def water_text(fire):
    w = fire.get("water")
    if w == "보도":
        return f"💧 아래층 물 피해 보도 ({fire.get('water_why', '')}) → 누수복구 영업"
    if w == "가능":
        return f"💧 아래층 물 피해 가능 ({fire.get('water_why', '')}) → 누수복구 영업"
    return ""


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


# ── 신빙성 ───────────────────────────────────────────────
def trust(fire):
    """공식 기록인지, 언론 몇 곳이 보도했는지로 신빙성을 정합니다."""
    presses = {n.get("press") for n in fire.get("news", []) if n.get("press")}
    if fire.get("source") in OFFICIAL:
        return "공식+보도" if presses else "공식"
    return "보도" if len(presses) >= 2 else "미확인"


def _seed_own_article(fire):
    """뉴스로 잡힌 건은 처음 알림의 기사를 '이미 본 기사'로 넣어 둡니다.
    (같은 기사를 '새 기사'로 다시 보내지 않으려고)"""
    if "news" in fire or fire.get("source") in OFFICIAL or not fire.get("title"):
        return
    title, _, press = fire["title"].rpartition(" - ")
    if not title:
        title, press = fire["title"], ""
    if fire.get("source") != "구글뉴스":
        press = press or fire["source"]          # 인천일보 등 지역 언론
    fire["news"] = [{"title": title, "press": press, "url": fire.get("url") or ""}]


# ── 네이버 (주소 맞는 글만 모아 그대로 보여주기) ─────────────
def _naver_query(fire):
    city, dong, bld = _names(fire)
    return (f"{bld} 화재" if bld else f"{city} {dong} 화재").strip()


def _link_id(url):
    """이미 보낸 글인지 알아보기 위한 짧은 번호 (글 내용은 저장하지 않음)."""
    return hashlib.sha1((url or "").encode()).hexdigest()[:10]


def _naver_fresh(fire, found):
    """처음 보는 네이버 글만 남기고, 종류별 누적 건수를 기록합니다."""
    seen = set(fire.get("naver_seen", []))
    fresh, counts = {}, dict(fire.get("naver_count", {}))
    for kind, items in found.items():
        new = []
        for it in items:
            lid = _link_id(it["url"])
            if lid not in seen:
                seen.add(lid)
                new.append(it)
        if new:
            fresh[kind] = new
            counts[kind] = counts.get(kind, 0) + len(new)
    fire["naver_seen"] = sorted(seen)
    fire["naver_count"] = counts
    return fresh


# ── 메인 ─────────────────────────────────────────────────
def run(fires):
    """fires: 저장 직전의 전체 목록. 규모·신빙성을 갱신하고, 바뀐 건은 재발송."""
    now = datetime.now(KST)
    targets = [f for f in fires if _in_window(f, now)]
    print(f"[F] 추적 대상 {len(targets)}건 (발생 {FOLLOW_HOURS}시간 이내)")

    # 대상별 기사 검색을 동시에 진행 (실행 시간 단축)
    def gather(f):
        since = _parse_time(f.get("published")) - timedelta(minutes=30)
        found = []
        for q in _queries(f):
            found += [n for n in _google_news(q, since) if _related(n["title"], f)]
        naver = naver_links.matching(_naver_query(f),
                                     lambda title: _related(title, f), since)
        return found, naver

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(gather, targets))

    changed = 0
    naver_total = 0
    for f, (found, naver) in zip(targets, results):
        _seed_own_article(f)
        # 이미 본 기사와 합칩니다 (같은 제목은 한 번만)
        known = {n["title"] for n in f.get("news", [])}
        fresh = [n for n in found if n["title"] not in known]
        fresh = list({n["title"]: n for n in fresh}.values())
        f["news"] = (f.get("news", []) + fresh)[:MAX_NEWS]
        f["trust"] = trust(f)
        naver_new = _naver_fresh(f, naver)
        naver_total += sum(len(v) for v in naver_new.values())

        # 규모 판정: 구글 뉴스 + 네이버 뉴스 제목 (블로그는 표현이 부정확해 제외)
        # 네이버 제목은 저장하지 않고 이번 회차 검색 결과로만 봅니다.
        # (등급은 내려가지 않으니 매 회차 다시 찾아도 충분합니다)
        titles = [n["title"] for n in f["news"]]
        titles += [it["title"] for it in naver.get("뉴스", [])
                   if it["title"] not in titles]
        new_size, why = judge(titles)
        old_size = f.get("size", "불명")
        f.setdefault("size", old_size)

        # 한 번 올라간 등급은 내리지 않습니다 (기사마다 표현이 달라 오락가락 방지)
        size_up = RANK[new_size] > RANK[old_size]
        if size_up:
            f["size"], f["size_why"] = new_size, why
        f["size_news"] = len(titles)
        extra = extra_checks(f, titles)        # 진화 상태·발화 층·아래층 물 피해

        if size_up or fresh or naver_new or extra:
            changed += 1
            print(f"    -> {f.get('region')} : {old_size} → {f['size']} {why} / "
                  f"새 기사 구글 {len(fresh)}건, 네이버 "
                  f"{ {k: len(v) for k, v in naver_new.items()} }")
            notify.send_update(f, _update_text(f, old_size, fresh, naver_new))

    print(f"    -> 네이버 새 글 {naver_total}건 · 업데이트 {changed}건 재발송")


def _update_text(f, old_size, fresh, naver_new):
    size = f["size"]
    head = (f"🔄 규모 업데이트: {LABEL[old_size]} → {LABEL[size]}"
            if size != old_size else f"🔄 새 소식 · 규모 {LABEL[size]}")
    lines = [
        head,
        f"📍 {f.get('region') or ''} {f.get('building') or ''}".strip(),
        f"신빙성: {TRUST_LABEL[f['trust']]}",
    ]
    if f.get("size_why"):
        lines.append(f"근거: {', '.join(f['size_why'])} (기사 {f.get('size_news', 0)}건)")
    if f.get("out"):
        lines.append(f"진화: {OUT_LABEL[f['out']]}")
    if floor_text(f):
        lines.append(f"🏢 층: {floor_text(f)}")
    if water_text(f):
        lines.append(water_text(f))
    if fresh:
        lines.append("")
        lines.append("🆕 새 기사")
    for n in fresh[:3]:
        press = f" - {n['press']}" if n.get("press") else ""
        lines.append(f"· {n['title']}{press}\n  {n['url']}")

    # 네이버: 판정에 쓰지 않고 제목·링크만 그대로 보여줍니다.
    icon = {"뉴스": "📰", "블로그": "📝"}
    for kind, items in naver_new.items():
        lines.append("")
        lines.append(f"{icon[kind]} 네이버 {kind}")
        for it in items[:3]:
            lines.append(f"· {it['title']}\n  {it['url']}")
    return "\n".join(lines)
