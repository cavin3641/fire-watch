# -*- coding: utf-8 -*-
"""
메인 실행 파일.  터미널에서:  python collect.py

흐름:  수집 -> 걸러내기 -> 좌표 붙이기 -> 저장 -> 알림
"""
import json
import os
from datetime import datetime, timezone, timedelta

import config
import filters
import geocode
import notify
from sources import google_news, naver_news, disaster_msg, local_news

KST = timezone(timedelta(hours=9))


def load_previous():
    """이미 알림 보낸 건은 다시 안 보내려고 기존 파일을 읽습니다."""
    if not os.path.exists(config.OUTPUT_JSON):
        return []
    try:
        with open(config.OUTPUT_JSON, encoding="utf-8") as f:
            return json.load(f).get("fires", [])
    except Exception:
        return []


def collect_all():
    """1단계 - 모든 곳에서 소식을 긁어옵니다."""
    items = []

    print("[1] 재난문자 확인 중...")
    items += disaster_msg.fetch()

    print("[2] 구글 뉴스 확인 중...")
    for kw in config.SEARCH_KEYWORDS:
        items += google_news.fetch(kw)
    print("[2-1] 지역 언론 확인 중...")
    items += local_news.fetch()

    print("[3] 네이버 뉴스 확인 중...")
    for kw in config.SEARCH_KEYWORDS:
        items += naver_news.fetch(kw)

    print(f"    -> 총 {len(items)}건 수집")
    return items


def process(items):
    """2단계 - 걸러내고, 중복 지우고, 좌표를 붙입니다."""
    fires = [it for it in items if filters.is_fire_news(it)]
    print(f"[4] 화재 관련만 추림 -> {len(fires)}건")

    for f in fires:
        f["region"] = filters.extract_region(f)

    fires = filters.dedupe(fires)
    print(f"[5] 중복 제거 -> {len(fires)}건")

    # 수도권 것만 남깁니다 (좌표 변환 전에 걸러야 호출 수를 아낍니다)
    in_area = [f for f in fires
               if f.get("region")
               and any(f["region"].startswith(s) for s in config.TARGET_SIDO)]
    print(f"[6] 수도권({'/'.join(config.TARGET_SIDO)}) -> {len(in_area)}건")

    print("[7] 좌표 변환 중...")
    located = []
    for f in in_area:
        coords = geocode.to_coords(f.get("region"))
        if not coords:
            continue                      # 위치를 못 찾으면 지도에 못 올립니다
        f["lat"], f["lon"] = coords
        f["distance_km"] = geocode.distance_km(*coords)
        if config.MAX_DISTANCE_KM and f["distance_km"] > config.MAX_DISTANCE_KM:
            continue
        located.append(f)

    print(f"    -> 좌표 확보 {len(located)}건")
    return located


def merge_and_trim(previous, current):
    """기존 목록에 새 것을 합치고, 오래된 건 버립니다.

    이렇게 해야 지도에 최근 이틀치가 쌓여서 보입니다.
    이번 회차에 뉴스가 안 잡혀도 어제 것이 사라지지 않습니다.
    """
    merged = {f["id"]: f for f in previous}
    for f in current:
        merged[f["id"]] = f          # 같은 사건이면 최신 내용으로 덮어씀

    cutoff = datetime.now(KST) - timedelta(hours=config.KEEP_HOURS)
    kept = []
    for f in merged.values():
        seen = f.get("first_seen")
        if not seen:
            kept.append(f)
            continue
        try:
            if datetime.fromisoformat(seen) >= cutoff:
                kept.append(f)
        except ValueError:
            kept.append(f)

    kept.sort(key=lambda x: x.get("first_seen") or "", reverse=True)
    return kept


def save(fires):
    """3단계 - 지도가 읽을 파일로 저장합니다."""
    os.makedirs(os.path.dirname(config.OUTPUT_JSON), exist_ok=True)
    payload = {
        "updated_at": datetime.now(KST).isoformat(),
        "fires": fires,
    }
    with open(config.OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[8] 저장 완료 -> {config.OUTPUT_JSON} ({len(fires)}건)")


def main():
    previous = load_previous()
    previous_ids = {f.get("id") for f in previous}

    items = collect_all()
    fires = process(items)

    now = datetime.now(KST).isoformat()
    new_ones = []
    for f in fires:
        if f["id"] not in previous_ids:
            f["first_seen"] = now     # 우리가 처음 본 시각
            new_ones.append(f)

    save(merge_and_trim(previous, fires))

    print(f"[9] 새 소식 {len(new_ones)}건 알림 발송")
    for f in new_ones:
        notify.send(notify.format_alert(f))


if __name__ == "__main__":
    main()
