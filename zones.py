# -*- coding: utf-8 -*-
"""
권역 나누기 — 담당자별로 텔레그램을 따로 보내기 위한 설정

[사장님이 하실 일]
1. 텔레그램에서 권역마다 그룹을 하나씩 만듭니다.
   예) "화재알림-경기북부" 그룹 생성 → 봇을 초대 → 담당자 초대
2. 각 그룹의 chat id 를 확인합니다.
   그룹에 아무 말이나 보낸 뒤 아래 주소를 브라우저에 입력:
   https://api.telegram.org/bot<토큰>/getUpdates
   → "chat":{"id":-1001234567890  ← 그룹은 보통 마이너스(-)로 시작합니다
3. GitHub Secrets 에 아래 이름으로 등록합니다.
      TELEGRAM_CHAT_GYEONGGI_NORTH
      TELEGRAM_CHAT_GYEONGGI_WEST
      TELEGRAM_CHAT_GYEONGGI_EAST
      TELEGRAM_CHAT_GYEONGGI_SOUTH
      TELEGRAM_CHAT_SEOUL_NORTH
      TELEGRAM_CHAT_SEOUL_SOUTH
      TELEGRAM_CHAT_INCHEON

   등록하지 않은 권역은 기존 TELEGRAM_CHAT_ID(사장님 방)로 갑니다.
"""
import os

# ── 서울: 한강 기준 ────────────────────────────────────
SEOUL_NORTH = [
    "종로", "중구", "용산", "성동", "광진", "동대문", "중랑",
    "성북", "강북", "도봉", "노원", "은평", "서대문", "마포",
]
SEOUL_SOUTH = [
    "양천", "강서", "구로", "금천", "영등포", "동작",
    "관악", "서초", "강남", "송파", "강동",
]

# ── 경기: 사무실(고양) 기준으로 나눔 ────────────────────
GYEONGGI_NORTH = [           # 사무실 권역 — 가장 가깝습니다
    "고양", "파주", "양주", "의정부", "동두천", "연천", "포천",
]
GYEONGGI_WEST = [
    "김포", "부천", "광명", "시흥", "안산",
]
GYEONGGI_EAST = [
    "남양주", "구리", "하남", "가평", "양평", "광주", "이천", "여주",
]
GYEONGGI_SOUTH = [           # 물량이 가장 많은 곳
    "수원", "성남", "용인", "안양", "군포", "의왕", "과천",
    "화성", "평택", "오산", "안성",
]

# 권역 이름 -> 환경변수 이름
ZONE_ENV = {
    "서울 북부": "TELEGRAM_CHAT_SEOUL_NORTH",
    "서울 남부": "TELEGRAM_CHAT_SEOUL_SOUTH",
    "인천": "TELEGRAM_CHAT_INCHEON",
    "경기 북부": "TELEGRAM_CHAT_GYEONGGI_NORTH",
    "경기 서부": "TELEGRAM_CHAT_GYEONGGI_WEST",
    "경기 동부": "TELEGRAM_CHAT_GYEONGGI_EAST",
    "경기 남부": "TELEGRAM_CHAT_GYEONGGI_SOUTH",
}

# 사무실 권역 — 알림에 표시를 붙입니다
HOME_ZONE = "경기 북부"


def zone_of(region):
    """지역명을 보고 어느 권역인지 알려줍니다."""
    r = region or ""

    if r.startswith("인천"):
        return "인천"

    if r.startswith("서울"):
        for g in SEOUL_NORTH:
            if g in r:
                return "서울 북부"
        for g in SEOUL_SOUTH:
            if g in r:
                return "서울 남부"
        return "서울 북부"          # 못 찾으면 북부로

    if r.startswith("경기"):
        for name, lst in (("경기 북부", GYEONGGI_NORTH),
                          ("경기 서부", GYEONGGI_WEST),
                          ("경기 동부", GYEONGGI_EAST),
                          ("경기 남부", GYEONGGI_SOUTH)):
            for g in lst:
                if g in r:
                    return name
        return "경기 남부"          # 못 찾으면 남부로

    return "기타"


def chat_id_of(zone):
    """그 권역의 텔레그램 방 번호. 없으면 None(기본방으로 감)."""
    env = ZONE_ENV.get(zone)
    if not env:
        return None
    return os.getenv(env, "").strip() or None
