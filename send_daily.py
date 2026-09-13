# -*- coding: utf-8 -*-
"""
아침 요약 보내기

매일 아침 7시에 실행되어, 어제 하루 화재를 정리해 보냅니다.
권역 방이 설정돼 있으면 각 방으로, 없으면 사장님 방으로 갑니다.

터미널에서:  python send_daily.py
"""
import json
import os

import config
import daily
import notify
import zones


def load_fires():
    if not os.path.exists(config.OUTPUT_JSON):
        print("fires.json 이 없습니다. collect.py 를 먼저 실행하세요.")
        return []
    with open(config.OUTPUT_JSON, encoding="utf-8") as f:
        return json.load(f).get("fires", [])


def main():
    fires = load_fires()
    if not fires:
        return

    active = daily.zones_with_fires(fires)
    print(f"어제 화재가 있던 권역: {active}")

    sent = 0
    for zone in active:
        text = daily.build_report(fires, zone=zone)
        chat = zones.chat_id_of(zone)
        if chat:
            notify.send(text, chat_id=chat)
            sent += 1
            # 사무실 권역은 사장님도 함께
            if zone == zones.HOME_ZONE:
                notify.send(text)
        else:
            # 권역 방이 없으면 사장님 방으로
            notify.send(text)
            sent += 1
        print(f"  {zone} 발송 완료")

    # 권역이 하나도 없으면 전체 요약이라도 보냅니다
    if not active:
        notify.send(daily.build_report(fires))
        print("  전체 요약 발송")

    print(f"총 {sent}건 발송")


if __name__ == "__main__":
    main()
