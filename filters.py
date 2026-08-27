# -*- coding: utf-8 -*-
"""
쓸모없는 소식을 걸러내고, 지역을 뽑아내고, 중복을 없앱니다.
정확도를 좌우하는 핵심 파일입니다.
"""
import hashlib
import re

import regions
from config import EXCLUDE_KEYWORDS

# ── 실제 '사건'임을 알려주는 말 ─────────────────────────
# 이 중 하나라도 없으면 홍보·통계·기업뉴스일 가능성이 큽니다
EVENT_WORDS = [
    # 불 자체
    "발생", "진화", "초진", "소실", "전소", "반소", "번져", "번졌",
    "불길", "불이 나", "불에 타", "타올라", "태워", "태우", "탔",
    "그을", "잿더미",
    # 사람
    "대피", "이송", "부상", "경상", "중상", "화상", "숨져", "사망",
    "연기흡입", "연기 흡입", "구조",
    # 대응·피해
    "출동", "진압", "초기 대응", "피해", "화재로",
]

# ── 명백히 우리와 무관한 소식 ───────────────────────────
NOISE_WORDS = [
    # 소방서 홍보·행사
    "안심콜", "캠페인", "홍보", "당부", "컨설팅", "표창", "간담회",
    "교육", "훈련", "점검", "실증", "위촉", "기념식", "개교", "주년",
    "체험", "공모", "세미나", "토론회", "발대식", "협약", "시범",
    # 사후 미담·후원 기사 (화재 자체가 아님)
    "성금", "전달", "기부", "모금", "러브하우스", "온정", "힘 보태",
    "피해 농가", "피해 가구", "피해 주민", "난방 지원", "복구 지원",
    "의원", "의회", "행정사무감사",
    # 통계·분석 기사
    "통계", "5년간", "5년 간", "연평균", "집중 발생", "분석 결과",
    "증가세", "감소세", "실태",
    # 주식·기업
    "특징주", "테마", "주가", "상한가", "급등", "코스닥", "코스피",
    "상용화", "출시", "수주", "계약", "투자", "지원 나선다", "무상 지원",
    # 보험사 (삼성화재 등 '화재'가 회사 이름)
    "삼성화재", "현대해상", "DB손해보험", "KB손해보험", "메리츠화재",
    "롯데손해보험", "한화손해보험", "흥국화재", "농협손해보험",
    # 차량 화재 (건물 복구와 무관)
    "화물차", "승용차", "고속도로", "버스", "오토바이", "전기차",
    "트럭", "택시", "주차된 차", "차량에서",
    "전기자전거", "킥보드", "자전거", "이륜차",
    # 산불·들불
    "야산", "임야", "들불", "쓰레기", "논밭", "폐기물",
    # 해외
    "파키스탄", "미국", "일본", "중국", "러시아", "베트남", "태국",
    "인도", "프랑스", "독일", "영국", "필리핀", "대만", "호주",
    "캘리포니아", "도쿄", "베이징", "모스크바",
]

# 소방서·소방본부 자체 소식 (사건이 아니라 기관 활동)
AGENCY_PATTERN = re.compile(r"(소방서|소방본부|소방청|안전공사|소방재난본부)\s*[,장]")


def is_fire_news(item):
    """진짜 화재 '사건' 소식인지 판단합니다."""
    text = item.get("raw_text", "")

    # 재난문자는 그 자체가 사건이므로 통과
    if item.get("source") == "재난문자":
        return "화재" in text or "불" in text

    if "화재" not in text and "불" not in text:
        return False

    for bad in NOISE_WORDS:
        if bad in text:
            return False

    for bad in EXCLUDE_KEYWORDS:
        if bad in text:
            return False

    if AGENCY_PATTERN.search(text):
        return False

    # 사건을 나타내는 말이 하나는 있어야 합니다
    if not any(w in text for w in EVENT_WORDS):
        return False

    return True


# 읍·면·동 이름 (예: 무거동, 오남읍, 인지면)
DONG_PATTERN = re.compile(r"(?<![0-9])([가-힣]{2,4}(?:동|읍|면))(?:\s|서|에서|$|[,·…])")


def clean_title(text):
    """제목 끝의 ' - 언론사' 를 잘라냅니다.
    안 자르면 '남양주 화재 - 인천일보' 에서 인천을 지역으로 잘못 읽습니다."""
    return text.rsplit(" - ", 1)[0] if " - " in text else text


# 순서가 중요합니다. 위에 있는 것부터 맞춰보므로
# 구체적인 시설을 먼저 두고, '건물'처럼 두루뭉술한 말은 맨 뒤에 둡니다.
FACILITY = [
    "아파트", "공장", "창고", "마트", "상가", "빌라", "오피스텔",
    "모텔", "호텔", "숙박", "병원", "요양원", "학교", "시장",
    "편의점", "카페", "식당", "점포", "사무실", "공사장",
    "농막", "축사", "비닐하우스", "주택", "건물",
]


def _match_gun(text, candidates):
    """시군구 이름을 찾습니다.

    '부산 강서구'에서 '서구'가 먼저 걸리는 문제가 있어
    '강서구'처럼 접미사까지 붙여 먼저 맞춰봅니다.
    """
    ordered = sorted(candidates, key=len, reverse=True)
    for suffix in ("구", "시", "군"):
        for gun in ordered:
            if gun + suffix in text:
                return gun
    for gun in ordered:
        if gun in text:
            return gun
    return None


def extract_region(item):
    """제목에서 지역을 뽑아 '시도 시군구 읍면동' 형태로 돌려줍니다."""
    if item.get("region"):
        return item["region"]

    text = clean_title(item.get("raw_text", ""))

    # 1) 읍면동을 찾아둡니다 (있으면 위치가 훨씬 정확해집니다)
    m = DONG_PATTERN.search(text)
    dong = m.group(1) if m else None

    # 2) 전국에서 이름이 겹치지 않는 시군구를 먼저 찾습니다
    #    ("전남광주 광양시"를 광주광역시로 잘못 읽는 것을 막습니다)
    gun = _match_gun(text, regions.UNIQUE_SIGUNGU.keys())
    if gun:
        sido = regions.UNIQUE_SIGUNGU[gun]
        return " ".join(x for x in (sido, gun, dong) if x)

    # 3) 시도를 찾고, 그 안에서 시군구를 찾습니다
    for short, full in list(regions.SIDO_ALIASES.items()) + list(regions.SIDO.items()):
        if short in text:
            gun = _match_gun(text, regions.SIGUNGU.get(full, []))
            return " ".join(x for x in (full, gun, dong) if x)

    return None


def make_id(item):
    """같은 사건인지 판별할 지문을 만듭니다.

    언론사마다 제목이 달라서 제목으로는 중복을 못 잡습니다.
    '지역 + 시설종류 + 날짜'가 같으면 같은 사건으로 봅니다.
    (칠곡 스펀지공장 화재가 8개 언론사에 나와도 알림은 1번)
    """
    text = clean_title(item.get("raw_text", ""))
    facility = next((f for f in FACILITY if f in text), "기타")
    day = (item.get("published") or "")[:10]
    # 읍면동은 빼고 '시도 시군구'까지만 씁니다.
    # "울산 남구"와 "울산 남구 무거동"이 같은 사건이기 때문입니다.
    area = " ".join((item.get("region") or "").split()[:2])
    key = f"{area}|{facility}|{day}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


def dedupe(items):
    """중복 제거. 같은 사건은 하나만 남깁니다."""
    seen = {}
    for it in items:
        fid = make_id(it)
        if fid not in seen:
            it["id"] = fid
            seen[fid] = it
    return list(seen.values())
