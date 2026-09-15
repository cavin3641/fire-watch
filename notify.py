# -*- coding: utf-8 -*-
"""
텔레그램으로 알림 보내기

[직접 하실 일]
1. 텔레그램에서 @BotFather 검색 -> /newbot -> 토큰 받기
2. 만든 봇에게 아무 말이나 보낸 뒤
   https://api.telegram.org/bot<토큰>/getUpdates 를 브라우저에 입력 -> chat id 확인
3. 둘 다 .env 에 넣기
"""
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import requests

KST = timezone(timedelta(hours=9))

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
    src = fire.get("source") or ""
    is_msg = src == "재난문자"
    is_news = src not in ("재난문자", "소방출동")   # 구글뉴스·인천일보 등
    owner_only = not fire.get("forpartner", True)
    visit = fire.get("visit") or ""
    mark = {"방문가능": "✅ 방문 가능",
            "곧가능": "🕐 곧 가능 (진화 마무리 중)",
            "진화중": "⛔ 아직 진화 중"}.get(visit, "")

    lines = [f"[{zone}]{home}"]
    if owner_only:
        lines.append("👤 사장님 확인 건")
    if is_msg:
        lines.append("📢 긴급재난문자")
    elif is_news:
        lines.append(f"📰 뉴스 · {src}")
    lines.append(f"🔥 {head}{fire.get('region') or '위치 미상'}")
    if mark:
        lines.append(mark)
    if fire.get("building"):
        b = fire["building"]
        if fire.get("bkind"):
            b += f" ({fire['bkind']})"
        lines.append(f"🏢 {b}")

    # 화재 종류만 보여줍니다.
    # 출동 차수(1차·2차)는 소방 내부 용어라 표시하지 않습니다.
    # 다만 점수 계산에는 계속 씁니다.
    if fire.get("kind"):
        lines.append(fire["kind"])
    if is_msg:
        lines.append(fire.get("title", "")[:200])
    elif is_news:
        lines.append(fire.get("title", "")[:150])

    # 발생 시각 (몇 시간 전인지)
    pub = fire.get("published")
    if pub:
        try:
            t = datetime.fromisoformat(pub)
            if t.tzinfo is None:
                t = t.replace(tzinfo=KST)
            mins = int((datetime.now(KST) - t).total_seconds() // 60)
            if mins < 60:
                lines.append(f"{mins}분 전 발생")
            elif mins < 1440:
                lines.append(f"{mins // 60}시간 전 발생")
            else:
                lines.append(f"{mins // 1440}일 전 발생")
        except Exception:
            pass

    if fire.get("in_news"):
        lines.append("※ 언론 보도됨 - 경쟁 업체도 인지")

    # 지도 링크만 보냅니다.
    # 정보 출처(어느 사이트에서 얻는지)는 회사 자산이므로 노출하지 않습니다.
    lat, lon = fire.get("lat"), fire.get("lon")
    if lat and lon:
        # 건물 이름이 있으면 그걸 도착지 이름으로 씁니다
        spot = fire.get("building") or (fire.get("region") or "화재현장").split()[-1]
        name = quote(spot)
        lines.append("")
        # /link/to/ 는 길찾기 화면을 엽니다.
        # 카카오가 좌표를 주소로 바꿔서 도착지에 표시해 줍니다.
        # (/link/map/ 은 이름표만 찍혀서 주소가 안 나옵니다)
        lines.append(f"📍 위치 · 길찾기\nhttps://map.kakao.com/link/to/{name},{lat},{lon}")

    return "\n".join(lines)


def send_by_zone(fire, text):
    """건물 종류에 따라 보낼 곳을 정합니다.

    아파트·상가·주택  -> 권역 담당 파트너 방 (사장님도 함께)
    공장·숙박·요양병원·학교 -> 사장님 방만

    파트너에게는 자기가 감당할 수 있는 건만 보내야
    헤매지 않고 사고도 줄어듭니다.
    """
    zone = zones.zone_of(fire.get("region"))

    # 사장님이 직접 볼 건 (공장·숙박·요양병원·교육종교)
    if not fire.get("forpartner", True):
        send(text)
        return zone + " (사장님)"

    target = zones.chat_id_of(zone)
    if target:
        # 파트너 방에만 보냅니다.
        # 사장님 방에는 '사장님 전용 건'만 오도록 해서
        # 하루 40건에 묻히지 않게 합니다.
        send(text, chat_id=target)
    else:
        # 그 권역에 담당자 방이 아직 없으면 사장님이 받습니다
        send(text)
    return zone
