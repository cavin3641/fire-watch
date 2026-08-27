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

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def send(text):
    if not TELEGRAM_TOKEN:
        print("  [건너뜀] 텔레그램: 토큰이 없습니다")
        print("  --- 보낼 내용 ---")
        print(text)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": True,
        }, timeout=10)
        return True
    except Exception as e:
        print(f"  [실패] 텔레그램 발송: {e}")
        return False


def format_alert(fire):
    """알림 문구를 만듭니다. 여기 문구는 마음대로 바꾸세요."""
    lines = [f"🔥 {fire.get('region') or '위치 미상'}"]
    lines.append(fire.get("title", "")[:120])

    tail = []
    if fire.get("distance_km") is not None:
        tail.append(f"사무실에서 약 {fire['distance_km']}km")
    if fire.get("source"):
        tail.append(fire["source"])
    if tail:
        lines.append(" · ".join(tail))

    if fire.get("url"):
        lines.append(fire["url"])
    return "\n".join(lines)
