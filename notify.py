# -*- coding: utf-8 -*-
"""
텔레그램으로 알림 보내기

[직접 하실 일]
1. 텔레그램에서 @BotFather 검색 -> /newbot -> 토큰 받기
2. 만든 봇에게 아무 말이나 보낸 뒤
   https://api.telegram.org/bot<토큰>/getUpdates 를 브라우저에 입력 -> chat id 확인
3. 둘 다 .env 에 넣기
"""
import requests

import zones
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def send(text, chat_id=None):
    if not TELEGRAM_TOKEN:
        print("  [건너뜀] 텔레그램: 토큰이 없습니다")
        print("  --- 보낼 내용 ---")
        print(text)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": chat_id or TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": True,
        }, timeout=10)
        return True
    except Exception as e:
        print(f"  [실패] 텔레그램 발송: {e}")
        return False


def format_alert(fire):
    """알림 문구를 만듭니다. 여기 문구는 마음대로 바꾸세요."""
    zone = zones.zone_of(fire.get("region"))
    home = " ★사무실권역" if zone == zones.HOME_ZONE else ""
    grade = fire.get("grade") or ""
    head = f"{grade} " if grade else ""
    lines = [f"[{zone}]{home}",
             f"🔥 {head}{fire.get('region') or '위치 미상'}"]
    if fire.get("kind"):
        detail = fire["kind"]
        if fire.get("scope"):
            detail += f" · {fire['scope']}"
        lines.append(detail)
    if fire.get("source") != "소방출동":
        lines.append(fire.get("title", "")[:120])

    tail = []
    if fire.get("distance_km") is not None:
        tail.append(f"사무실에서 약 {fire['distance_km']}km")
    if fire.get("source"):
        tail.append(fire["source"])
    if tail:
        lines.append(" · ".join(tail))

    if fire.get("in_news"):
        lines.append("※ 뉴스 보도됨 - 경쟁 업체도 인지")
    if fire.get("news_url"):
        lines.append(fire["news_url"])
    elif fire.get("url"):
        lines.append(fire["url"])
    return "\n".join(lines)


def send_by_zone(fire, text):
    """그 화재가 속한 권역 방으로 보냅니다.

    권역 방이 설정돼 있지 않으면 기본 방(사장님)으로 갑니다.
    사무실 권역(경기 북부)은 권역 방과 기본 방 양쪽으로 보냅니다.
    """
    zone = zones.zone_of(fire.get("region"))
    target = zones.chat_id_of(zone)

    if target:
        send(text, chat_id=target)
        # 사무실 권역은 사장님도 같이 받습니다
        if zone == zones.HOME_ZONE and TELEGRAM_CHAT_ID != target:
            send(text)
    else:
        send(text)
    return zone
