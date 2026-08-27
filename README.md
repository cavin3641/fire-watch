# 화재 현장 실시간 알림 (fire-watch)

화재 소식을 10분마다 자동으로 모아서 **텔레그램 알림 + 지도**로 보여줍니다.

---

## 폴더 구조

```
fire-watch/
├── collect.py            ★ 실행 파일 (이것만 돌리면 됨)
├── config.py             ★ 설정 (키워드, 반경, 기준 위치)
├── .env                  ★ API 키 보관 (직접 만들어야 함)
├── .env.example             .env 예시
├── requirements.txt         필요한 패키지 목록
│
├── sources/                 ── 소식을 긁어오는 곳 ──
│   ├── google_news.py       구글 뉴스 (키 불필요, 지금 동작함)
│   ├── naver_news.py        네이버 뉴스 (키 필요)
│   └── disaster_msg.py      재난문자 (키 + 승인 필요)
│
├── filters.py               쓸모없는 소식 걸러내기 + 중복 제거
├── geocode.py               지역명 -> 위도·경도 변환
├── notify.py                텔레그램 발송
│
├── docs/                    ── 웹페이지 (GitHub Pages) ──
│   ├── index.html           지도 화면
│   └── fires.json           수집 결과 (자동 생성)
│
└── .github/workflows/
    └── collect.yml          10분마다 자동 실행 설정
```

---

## 처음 실행해 보기 (키 없이)

```bash
pip install -r requirements.txt
python collect.py
```

키가 하나도 없어도 **구글 뉴스는 수집됩니다.** 좌표 변환만 안 되니
카카오 키를 먼저 넣으면 지도까지 바로 볼 수 있습니다.

---

## 직접 하실 일 (순서대로)

### 1. 카카오 키 — 지도를 켜는 열쇠
- developers.kakao.com 가입 → 애플리케이션 추가
- **REST API 키** → `.env` 의 `KAKAO_REST_KEY`
- **JavaScript 키** → `docs/index.html` 의 `YOUR_JAVASCRIPT_KEY` 자리
- 앱 설정 → 플랫폼 → Web 에 사이트 주소 등록 (안 하면 지도가 안 뜹니다)

### 2. 텔레그램 봇 — 휴대폰 알림
- 텔레그램에서 `@BotFather` → `/newbot` → 토큰 받기
- 봇에게 아무 말이나 보낸 뒤
  `https://api.telegram.org/bot<토큰>/getUpdates` 접속 → `chat id` 확인
- 둘 다 `.env` 에 넣기

### 3. 네이버 검색 API
- developers.naver.com → 애플리케이션 등록 → **검색** 선택
- Client ID / Secret 을 `.env` 에

### 4. 재난문자 API (가장 오래 걸림)
- safetydata.go.kr 가입 → **행정안전부_긴급재난문자** 활용신청
- 승인 후 서비스키를 `.env` 에
- **중요**: `sources/disaster_msg.py` 의 `API_PATH` 와 응답 필드명을
  신청 페이지의 규격서와 반드시 대조해서 맞추세요

### 5. 자동 실행 (선택)
- GitHub 저장소 만들고 코드 올리기
- Settings → Secrets and variables → Actions 에 키 6개 등록
- Settings → Pages → Source: `main` 브랜치 `/docs` 폴더
- 완료되면 `아이디.github.io/저장소이름` 에서 지도가 열립니다

---

## 앞으로 손봐야 할 곳 (코드에 `TODO` 로 표시해 뒀습니다)

| 파일 | 할 일 |
|---|---|
| `filters.py` | 과거 기사·해외 뉴스 걸러내기, 같은 사건 기사 묶기 |
| `collect.py` | 48시간 지난 항목 목록에서 빼기 |
| `sources/disaster_msg.py` | 실제 API 경로·필드명 맞추기 |
| `config.py` | 제외 키워드를 쓰면서 계속 추가 |

---

## 알아두실 점

- 개인 주택 화재는 뉴스에 거의 안 나옵니다. 공장·상가·아파트 위주로 잡힙니다.
- 위치는 "○○구 ○○동" 수준까지입니다. 번지는 나오지 않습니다.
- GitHub Actions 는 10분 간격이지만 몇 분 더 늦어질 수 있습니다.
  더 빠른 알림이 필요하면 사무실 PC 에서 1분마다 돌리는 방식으로 바꾸세요.
