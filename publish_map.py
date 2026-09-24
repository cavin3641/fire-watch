# -*- coding: utf-8 -*-
"""
지도 공개용 파일 만들기 (암호화)

코드 저장소(fire-watch)는 비공개로 두고,
지도는 별도 공개 저장소(fire-map)에 '암호화된 데이터'만 올립니다.
비밀번호를 모르면 화재 주소·건물명을 볼 수 없습니다.

결과물: map_out/index.html , map_out/fires.enc
"""
import base64
import json
import os
import shutil

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import config

OUT = "map_out"
ITER = 200_000                  # 지도 페이지(index.html)와 같은 값이어야 함

# 지도에 필요 없는 내부 정보는 빼고 올립니다
DROP_KEYS = ("tg", "url", "raw_text")


def main():
    pw = os.getenv("MAP_PASSWORD", "")
    if len(pw) < 8:
        raise SystemExit("MAP_PASSWORD 가 없거나 너무 짧습니다 (8자 이상)")

    with open(config.OUTPUT_JSON, encoding="utf-8") as f:
        data = json.load(f)
    for fire in data.get("fires", []):
        for k in DROP_KEYS:
            fire.pop(k, None)
    plain = json.dumps(data, ensure_ascii=False).encode("utf-8")

    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=ITER).derive(pw.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, plain, None)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "fires.enc"), "w") as f:
        json.dump({"salt": base64.b64encode(salt).decode(),
                   "iv": base64.b64encode(iv).decode(),
                   "ct": base64.b64encode(ct).decode()}, f)
    shutil.copy("docs/index.html", os.path.join(OUT, "index.html"))
    print(f"[M] 암호화 지도 파일 생성 -> {OUT}/ ({len(data.get('fires', []))}건)")


if __name__ == "__main__":
    main()
