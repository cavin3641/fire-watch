# -*- coding: utf-8 -*-
"""
국민안전24 소방정보 (소방청 제공 119 출동정보)

뉴스에 안 나오는 작은 화재까지 전부 잡히는 곳입니다.
경기도만 하루 50건 이상 나옵니다.

[중요] 상세주소(번지)는 일부러 쓰지 않습니다.
       국민안전24는 개인 주거지 노출을 막기 위해 화면에
       읍·면·동까지만 표시합니다. 그 방침을 따릅니다.
"""
import time
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta

import requests
from pyproj import Transformer

KST = timezone(timedelta(hours=9))

URL = "https://www.safekorea.go.kr/safekorea-kor/ctim/csim/fireInfoDataList.do"
HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.safekorea.go.kr/safekorea-kor/ctim/csim/fireInfo.do",
    "User-Agent": "Mozilla/5.0 (fire-watch)",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

# 시도 코드
SIDO = {
    "11": "서울특별시",
    "28": "인천광역시",
    "41": "경기도",
}

# 소방청 좌표계(EPSG:5186) -> 위경도(EPSG:4326) 변환기
_TRANS = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)


def _to_latlon(gis_x, gis_y, region):
    """소방청 좌표를 지도에 찍을 위경도로 바꿉니다.

    사이트 자바스크립트와 동일하게 지역별 보정을 먼저 합니다.
    이 좌표는 읍면동 중심이 아니라 실제 출동 지점입니다.
    """
    if not gis_x or not gis_y:
        return None
    x, y = float(gis_x), float(gis_y)

    if any(k in region for k in ("경기", "인천", "서울", "강원")):
        if y < 480000:
            y += 100000
    elif any(k in region for k in ("충청", "세종", "대전", "전라북도")):
        if y < 390000:
            y += 100000
    elif any(k in region for k in ("전라남도", "경상남도", "대구", "부산", "울산", "광주")):
        if y < 250000:
            y += 100000
    elif "경상북도" in region:
        if y < 350000:
            y += 100000
    elif "제주" in region:
        if y < 50000:
            y += 50000

    try:
        lon, lat = _TRANS.transform(x, y)
    except Exception:
        return None
    # 한반도 밖이면 버립니다
    if not (33 < lat < 39 and 124 < lon < 132):
        return None
    return lat, lon


MAX_PAGES = 12          # 시도당 최대 페이지 (한 페이지 5건 -> 최대 60건)
SLEEP_SEC = 0.7         # 사이트에 부담 주지 않도록 쉬어 갑니다


def _parse_time(s):
    """20260829101730 -> 2026-08-29T10:17:30+09:00"""
    if not s or len(s) < 14:
        return None
    try:
        dt = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
        return dt.replace(tzinfo=KST).isoformat()
    except ValueError:
        return None


def _fetch_page(gubun, page):
    # 한글 파라미터는 UTF-8로 직접 인코딩해서 보냅니다
    body = urlencode({"page": str(page), "gubun": gubun, "param": "화재"},
                     encoding="utf-8")
    res = requests.post(URL, headers=HEADERS, data=body.encode("utf-8"),
                        timeout=30)
    res.raise_for_status()
    return res.json()


def fetch():
    results = []

    for gubun, sido_name in SIDO.items():
        got = 0
        for page in range(1, MAX_PAGES + 1):
            try:
                payload = _fetch_page(gubun, page)
            except Exception as e:
                print(f"  [실패] 소방정보 {sido_name} {page}쪽: {type(e).__name__}")
                break

            rows = payload.get("list") or []
            if not rows:
                break

            for row in rows:
                # 읍·면·동까지만 사용합니다 (상세주소는 쓰지 않습니다)
                region = (row.get("dstrAreaNm") or "").strip()
                kind = (row.get("pttnNm2") or "화재").strip()
                if not region:
                    continue

                coords = _to_latlon(row.get("gisX"), row.get("gisY"), region)

                item = {
                    "source": "소방출동",
                    "title": f"{kind} - {region}",
                    "url": "https://www.safekorea.go.kr/safekorea-kor/ctim/csim/fireInfo.do",
                    "published": _parse_time(row.get("reptDt")),
                    "region": region,
                    "kind": kind,
                    "raw_text": f"{kind} {region} 화재 발생",
                }
                if coords:
                    item["lat"], item["lon"] = coords
                results.append(item)
                got += 1

            if page >= payload.get("totalPages", 1):
                break
            time.sleep(SLEEP_SEC)

        print(f"  소방정보 {sido_name} {got}건")

    return results
