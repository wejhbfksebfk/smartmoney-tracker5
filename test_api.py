"""
KIS API 연결 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━
실행: python test_api.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import requests
import json

print("=" * 50)
print("  KIS API 연결 테스트")
print("=" * 50)

APP_KEY    = input("\nAPP KEY    입력: ").strip()
APP_SECRET = input("APP SECRET 입력: ").strip()
IS_REAL    = input("실전투자? [Y/n]  : ").strip().lower() != "n"

BASE = "https://openapi.koreainvestment.com:9443" if IS_REAL \
  else "https://openapivts.koreainvestment.com:29443"

print(f"\n접속 서버: {BASE}")
print(f"APP KEY  : {APP_KEY[:4]}****{APP_KEY[-4:] if len(APP_KEY)>8 else ''}")
print(f"계좌구분 : {'실전' if IS_REAL else '모의'}\n")

# ── STEP 1: 토큰 발급 ──────────────────────────────────────
print("[STEP 1] 토큰 발급 시도...")
try:
    r = requests.post(
        f"{BASE}/oauth2/tokenP",
        json={
            "grant_type": "client_credentials",
            "appkey":     APP_KEY,
            "appsecret":  APP_SECRET,
        },
        timeout=15,
    )
    print(f"  HTTP 상태: {r.status_code}")
    print(f"  응답 본문: {r.text[:300]}")

    if r.status_code == 200:
        token = r.json().get("access_token", "")
        print(f"\n  ✅ 토큰 발급 성공! ({token[:20]}...)")
    elif r.status_code == 403:
        print("\n  ❌ 403 Forbidden")
        print("  원인 1: APP KEY/SECRET 불일치")
        print("  원인 2: 실전/모의 서버 구분 오류")
        print("  원인 3: KIS 앱이 비활성 상태")
    elif r.status_code == 401:
        print("\n  ❌ 401 Unauthorized — KEY/SECRET 오류")
    else:
        print(f"\n  ❌ 예상치 못한 오류: {r.status_code}")

except requests.exceptions.ConnectionError as e:
    print(f"\n  ❌ 연결 실패: {e}")
    print("  → 네트워크 또는 방화벽 문제일 수 있습니다")
except requests.exceptions.Timeout:
    print("\n  ❌ 타임아웃 — 서버 응답 없음")
except Exception as e:
    print(f"\n  ❌ 오류: {e}")

print("\n" + "=" * 50)
input("엔터를 누르면 종료합니다...")
