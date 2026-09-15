# -*- coding: utf-8 -*-
"""
아침 일일 요약

매일 아침, 어제 하루 동안 난 화재를 정리해서 한 번에 보냅니다.
실시간 알림은 그때그때 오지만, 밤새 온 것을 놓치거나
몰아서 보기 어렵기 때문에 아침에 한 장으로 정리해 드립니다.

권역별로 각자의 방에 보냅니다.
"""
from datetime import datetime, timezone, timedelta

from urllib.parse import quote

import zones

KST = timezone(timedelta(hours=9))


def _yesterday_range():
    """어제 0시부터 오늘 0시까지."""
    now = datetime.now(KST)
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today0 - timedelta(days=1), today0


def _pick(fires, start, end):
    """어제 발생한 건만 고릅니다."""
    out = []
    for f in fires:
        p = f.get("published")
        if not p:
            continue
        try:
            t = datetime.fromisoformat(p)
            if t.tzinfo is None:
                t = t.replace(tzinfo=KST)
        except ValueError:
            continue
        if start <= t < end:
            out.append(f)
    return out


def build_report(fires, zone=None, partner_only=False):
    """어제 화재 요약문을 만듭니다.

    zone         : 그 권역만
    partner_only : True 면 영업 파트너가 갈 건물만 (아파트·상가·주택)
    """
    start, end = _yesterday_range()
    items = _pick(fires, start, end)

    if zone:
        items = [f for f in items if zones.zone_of(f.get("region")) == zone]
    if partner_only:
        items = [f for f in items if f.get("forpartner", True)]

    date_str = start.strftime("%m월 %d일")
    head = f"📋 {date_str} 화재 정리"
    if zone:
        head += f" · {zone}"

    if not items:
        return f"{head}\n\n어제는 잡힌 화재가 없었습니다."

    # 방문 가능한 것부터, 점수 높은 순
    items.sort(key=lambda x: (x.get("visit") != "방문가능", -(x.get("score") or 0)))

    visitable = [f for f in items if f.get("visit") == "방문가능"]
    lines = [head, ""]
    lines.append(f"전체 {len(items)}건 · 방문 가능 {len(visitable)}건")
    lines.append("")

    # 건물 종류별 집계
    kinds = {}
    for f in items:
        k = f.get("bkind") or "종류 미상"
        kinds[k] = kinds.get(k, 0) + 1
    if kinds:
        summary = " · ".join(f"{k} {v}" for k, v in
                             sorted(kinds.items(), key=lambda x: -x[1]))
        lines.append(summary)
        lines.append("")

    lines.append("─" * 18)

    # 상위 10건만 자세히
    for i, f in enumerate(items[:10], 1):
        grade = f.get("grade") or ""
        mark = "✅" if f.get("visit") == "방문가능" else "⛔"
        lines.append("")
        lines.append(f"{i}. {mark} {grade} {f.get('region') or '위치 미상'}")

        if f.get("building"):
            b = f["building"]
            if f.get("bkind"):
                b += f" ({f['bkind']})"
            lines.append(f"   🏢 {b}")

        src = f.get("source") or ""
        if src == "재난문자":
            lines.append("   📢 긴급재난문자")
        elif src not in ("소방출동", ""):
            lines.append(f"   📰 뉴스 · {src}")
        elif f.get("kind"):
            lines.append(f"   {f['kind']}")

        t = f.get("published")
        if t:
            try:
                dt = datetime.fromisoformat(t)
                lines.append(f"   {dt.strftime('%H:%M')} 발생")
            except ValueError:
                pass

        if f.get("lat") and f.get("lon"):
            spot = (f.get("building") or (f.get("region") or "화재현장").split()[-1])
            lines.append(f"   https://map.kakao.com/link/to/{quote(spot)},{f['lat']},{f['lon']}")

    if len(items) > 10:
        lines.append("")
        lines.append(f"…그 외 {len(items) - 10}건은 지도에서 확인하세요.")

    return "\n".join(lines)


def zones_with_fires(fires):
    """어제 화재가 있었던 권역 목록."""
    start, end = _yesterday_range()
    items = _pick(fires, start, end)
    return sorted({zones.zone_of(f.get("region")) for f in items})
