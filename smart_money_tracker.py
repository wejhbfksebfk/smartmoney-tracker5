"""
스마트 머니 트래커 v5.0  —  CLI 엔진
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
실행  : python smart_money_tracker.py
의존성: pip install requests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[v5.0 알고리즘 — 9개 시그널 (한투 KIS API 전용)]

매수 점수 (100점 만점)
  SIG-1  외국인 순매수 강도    20pt  수량 + 거래대금 기준
  SIG-2  기관 동반 여부        10pt  외국인+기관 동시 매수
  SIG-3  프로그램 동반 여부    10pt  외국인+프로그램 동시
  SIG-4  매수강도 급등         15pt  직전 스냅샷 대비 증가율
  SIG-5  연속 순매수일         10pt  외국인 3일 이상 연속 매수
  SIG-6  분봉 방향성           10pt  최근 5분봉 상승 추세
  SIG-7  바닥권 위치           10pt  52주 저점 30% 이내
  SIG-8  거래량 폭발           10pt  평균 대비 1.5배 이상
  SIG-9  황금시간대 보정        5pt  09:00~10:30 수집 가산

매도 경보 (100점 만점)
  SIG-A  수급 이탈 강도        35pt
  SIG-B  연속 순매도일         20pt
  SIG-C  고점권 + 분봉하락     25pt
  SIG-D  거래량 감소 + 하락    20pt
"""

import requests
import json
import time
import csv
import sys
import math
import collections
from datetime import datetime, date
from pathlib import Path

# ════════════════════════════════════════════════════════════
#  상수
# ════════════════════════════════════════════════════════════
CONFIG_FILE = Path("config.json")
TOKEN_FILE  = Path("token_cache.json")

BASE_REAL  = "https://openapi.koreainvestment.com:9443"
BASE_PAPER = "https://openapivts.koreainvestment.com:29443"

API_DELAY  = 0.08   # 초당 ~12건 (한투 제한 20건의 60%)

# ── 기본 필터 임계값 (config.json 에서 덮어쓸 수 있음) ──
DEFAULT_CFG = {
    "surge":      1.5,    # 매수강도 급등 배수
    "dual_bonus": 2.0,    # 동반매수 가산 계수
    "max_prdy":   3.0,    # 당일 등락률 절댓값 상한 (%)
    "from_52w":   30.0,   # 52주 저점 대비 상한 (%)
    "min_vol":    1.5,    # 최소 거래량 배수
    "threshold":  4.0,    # 최소 점수 기준 (×10 → 40점)
    "min_amt":    500,    # 최소 거래대금 (백만원) — 소형주 필터
    "tp":         5.0,    # 목표 수익률 (%)
    "sl":         3.0,    # 손절 기준 (%)
    "time_filter":True,   # 황금시간대 가산점 적용 여부
}


# ════════════════════════════════════════════════════════════
#  1. 인증 / 설정
# ════════════════════════════════════════════════════════════

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 설정 저장 → {CONFIG_FILE}\n")


def get_credentials() -> tuple[str, str, bool, dict]:
    """
    APP KEY / SECRET 반환.
    config.json 없으면 대화식 입력 후 저장.
    """
    raw = load_config()
    if raw.get("app_key") and raw.get("app_secret"):
        mode = "실전" if raw.get("real", True) else "모의"
        print(f"  🔑 저장된 인증 정보 로드 ({mode}투자)\n")
        # 필터 설정 병합
        cfg = {**DEFAULT_CFG, **raw.get("filter_cfg", {})}
        return raw["app_key"], raw["app_secret"], raw.get("real", True), cfg

    print("=" * 58)
    print("  한국투자증권 KIS API 인증 정보 설정")
    print("  발급: https://apiportal.koreainvestment.com")
    print("=" * 58)
    app_key    = input("  APP KEY    : ").strip()
    app_secret = input("  APP SECRET : ").strip()
    real_yn    = input("  실전투자?  [Y/n] : ").strip().lower()
    is_real    = (real_yn != "n")

    save_config({
        "app_key": app_key, "app_secret": app_secret,
        "real": is_real, "filter_cfg": {}
    })
    return app_key, app_secret, is_real, dict(DEFAULT_CFG)


def get_access_token(app_key: str, app_secret: str, base_url: str) -> str:
    if TOKEN_FILE.exists():
        cache = json.loads(TOKEN_FILE.read_text())
        if time.time() - cache.get("issued_at", 0) < 86000:
            print("  🔄 캐시 토큰 사용\n")
            return cache["access_token"]

    print("  🔐 액세스 토큰 발급 중...")
    resp = requests.post(
        f"{base_url}/oauth2/tokenP",
        json={"grant_type": "client_credentials",
              "appkey": app_key, "appsecret": app_secret},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError(f"토큰 발급 실패: {resp.json()}")

    TOKEN_FILE.write_text(
        json.dumps({"access_token": token, "issued_at": time.time()})
    )
    print("  ✅ 토큰 발급 완료\n")
    return token


# ════════════════════════════════════════════════════════════
#  2. 공통 HTTP 래퍼
# ════════════════════════════════════════════════════════════

def make_headers(token: str, app_key: str, app_secret: str, tr_id: str) -> dict:
    return {
        "Content-Type":  "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey":         app_key,
        "appsecret":      app_secret,
        "tr_id":          tr_id,
        "custtype":       "P",
    }


def safe_get(url: str, headers: dict, params: dict,
             max_retry: int = 3) -> dict | None:
    for attempt in range(1, max_retry + 1):
        time.sleep(API_DELAY)
        try:
            resp = requests.get(url, headers=headers,
                                params=params, timeout=10)
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"    ⚠️  429 → {wait}s 대기 [{attempt}/{max_retry}]")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            d = resp.json()
            if d.get("rt_cd") != "0":
                return None
            return d
        except requests.exceptions.Timeout:
            time.sleep(1)
        except requests.exceptions.RequestException:
            time.sleep(1)
    return None


# ════════════════════════════════════════════════════════════
#  3. KIS API 수집 함수 (한투 전용)
# ════════════════════════════════════════════════════════════

def fetch_investor(token, app_key, app_secret, base_url,
                   inv: str = "FRG") -> list[dict]:
    """외국인/기관 순매수 상위 FHPST02060000"""
    url  = f"{base_url}/uapi/domestic-stock/v1/quotations/foreign-institution-total"
    code = "1" if inv == "FRG" else "2"
    out  = []
    for mkt in ["J", "Q"]:
        d = safe_get(url, make_headers(token, app_key, app_secret, "FHPST02060000"), {
            "fid_cond_mrkt_div_code": mkt, "fid_cond_scr_div_code": "16448",
            "fid_input_iscd": "0000",       "fid_div_cls_code": "1",
            "fid_rank_sort_cls_code": "0",  "fid_input_cnt_1": "50",
            "fid_etc_cls_code": code,
        })
        if d and d.get("output"):
            for row in d["output"]:
                row["_mkt"] = "KOSPI" if mkt == "J" else "KOSDAQ"
                out.append(row)
        time.sleep(0.1)
    return out


def fetch_program(token, app_key, app_secret, base_url) -> list[dict]:
    """프로그램 매매 순매수 상위 FHPST01710000"""
    url = f"{base_url}/uapi/domestic-stock/v1/quotations/program-trade-by-stock"
    out = []
    for mkt in ["J", "Q"]:
        d = safe_get(url, make_headers(token, app_key, app_secret, "FHPST01710000"), {
            "fid_cond_mrkt_div_code": mkt, "fid_cond_scr_div_code": "20171",
            "fid_input_iscd": "0000",       "fid_div_cls_code": "0",
            "fid_rank_sort_cls_code": "0",  "fid_input_cnt_1": "50",
        })
        if d and d.get("output"):
            for row in d["output"]:
                row["_mkt"] = "KOSPI" if mkt == "J" else "KOSDAQ"
                out.append(row)
        time.sleep(0.1)
    return out


def fetch_detail(token, app_key, app_secret, base_url,
                 iscd: str) -> dict | None:
    """종목 기본 시세 + 52주 고/저가 + 거래량 FHKST01010100"""
    url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
    d = safe_get(url, make_headers(token, app_key, app_secret, "FHKST01010100"),
                 {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": iscd})
    return d.get("output") if d else None


def fetch_vol_rank(token, app_key, app_secret, base_url) -> list[dict]:
    """거래량 순위 FHPST01050000"""
    url = f"{base_url}/uapi/domestic-stock/v1/quotations/volume-rank"
    out = []
    for mkt in ["J", "Q"]:
        d = safe_get(url, make_headers(token, app_key, app_secret, "FHPST01050000"), {
            "fid_cond_mrkt_div_code": mkt, "fid_cond_scr_div_code": "20171",
            "fid_input_iscd": "0000",       "fid_div_cls_code": "0",
            "fid_blng_cls_code": "0",       "fid_trgt_cls_code": "111111111",
            "fid_trgt_exls_cls_code": "000000",
            "fid_input_price_1": "1000",    "fid_input_price_2": "999999",
            "fid_vol_cnt": "100000",        "fid_input_date_1": "",
        })
        if d and d.get("output"):
            for row in d["output"]:
                row["_mkt"] = "KOSPI" if mkt == "J" else "KOSDAQ"
                out.append(row)
        time.sleep(0.1)
    return out


def fetch_investor_daily(token, app_key, app_secret, base_url,
                         iscd: str) -> list[dict]:
    """투자자별 일별 매매 동향 FHKST01010900 — 연속 순매수일 체크"""
    url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-investor"
    d = safe_get(url, make_headers(token, app_key, app_secret, "FHKST01010900"), {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd":         iscd,
        "fid_input_date_1":       "",
        "fid_input_date_2":       "",
        "fid_period_div_code":    "D",
    })
    if d and d.get("output"):
        return d["output"][:5]   # 최근 5거래일
    return []


def fetch_minute(token, app_key, app_secret, base_url,
                 iscd: str, n: int = 5) -> list[dict]:
    """주식 당일 분봉 FHKST03010200 — 분봉 방향성 판단"""
    url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    now = datetime.now().strftime("%H%M%S")
    d = safe_get(url, make_headers(token, app_key, app_secret, "FHKST03010200"), {
        "fid_etc_cls_code":       "",
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd":         iscd,
        "fid_input_hour_1":       now,
        "fid_pw_data_incu_yn":    "N",
    })
    if d and d.get("output2"):
        return d["output2"][:n]
    return []


# ════════════════════════════════════════════════════════════
#  4. 히스토리 (매수강도 급등 계산용)
# ════════════════════════════════════════════════════════════

_ntby_hist: dict[str, collections.deque] = {}


def push_hist(iscd: str, qty: int):
    if iscd not in _ntby_hist:
        _ntby_hist[iscd] = collections.deque(maxlen=10)
    _ntby_hist[iscd].append(qty)


def surge_ratio(iscd: str) -> float:
    h = _ntby_hist.get(iscd)
    if not h or len(h) < 2:
        return 1.0
    return h[-1] / max(abs(h[-2]), 1)


# ════════════════════════════════════════════════════════════
#  5. 유틸
# ════════════════════════════════════════════════════════════

def fv(v, d=0.0):
    try:    return float(str(v).replace(",", ""))
    except: return d

def iv(v, d=0):
    try:    return int(str(v).replace(",", ""))
    except: return d

def market_session() -> str:
    now = datetime.now()
    h, m = now.hour, now.minute
    total = h * 60 + m
    if now.weekday() >= 5:        return "closed"
    if total < 540 or total >= 930: return "closed"
    if 540 <= total < 630:        return "prime"
    if 870 <= total < 930:        return "caution"
    return "normal"


# ════════════════════════════════════════════════════════════
#  6. 매수 점수 — 9개 시그널
# ════════════════════════════════════════════════════════════

def calc_buy_score(iscd, qty, amt_mil, prdy, det,
                   is_org, is_prg, is_vol,
                   daily_hist, minute_bars,
                   cfg: dict, session: str):
    sigs = {}

    # SIG-1: 외국인 순매수 강도 (20pt)
    s1q = (10 if qty>=1_000_000 else 8 if qty>=500_000 else
           6 if qty>=200_000   else 4 if qty>=100_000  else
           2 if qty>=50_000    else 0)
    s1a = (10 if amt_mil>=5000 else 8 if amt_mil>=2000 else
           6 if amt_mil>=1000  else 4 if amt_mil>=500  else
           2 if amt_mil>=200   else 0)
    sigs["SIG1_수급강도"] = s1q + s1a

    # 거래대금 최소 필터
    if amt_mil < cfg["min_amt"]:
        return 0, "관망", False, sigs, [f"❌ 거래대금 {amt_mil:.0f}백만 < {cfg['min_amt']}백만"]

    # SIG-2: 기관 동반 (10pt)
    sigs["SIG2_기관동반"] = 10 if is_org else 0

    # SIG-3: 프로그램 동반 (10pt)
    sigs["SIG3_프로그램"] = 10 if is_prg else 0

    # SIG-4: 매수강도 급등 (15pt)
    sg = surge_ratio(iscd)
    sigs["SIG4_급등"] = (round(min(15.0, math.log2(max(sg, 1.001)) * 7.5), 1)
                         if sg >= cfg["surge"] else 0)

    # SIG-5: 연속 순매수일 (10pt)
    consec = 0
    for day in daily_hist:
        if iv(day.get("frgn_ntby_qty", day.get("frgn_seln_qty", 0))) > 0:
            consec += 1
        else:
            break
    sigs["SIG5_연속매수"] = (10 if consec>=5 else 7 if consec>=3
                              else 4 if consec>=2 else 2 if consec>=1 else 0)

    # SIG-6: 분봉 방향성 (10pt)
    s6 = 0
    if len(minute_bars) >= 3:
        closes = [fv(b.get("stck_prpr", b.get("stck_clpr", 0)))
                  for b in minute_bars[:5]]
        closes = [c for c in closes if c > 0]
        if len(closes) >= 3:
            rising = sum(1 for i in range(1, len(closes))
                         if closes[i] > closes[i-1])
            if rising >= len(closes) - 1: s6 = 10
            elif rising >= len(closes) // 2: s6 = 5
    sigs["SIG6_분봉방향"] = s6

    # SIG-7: 바닥권 위치 + 필터 (10pt)
    s7 = 0
    if det:
        w52l  = fv(det.get("w52_lwpr", 0))
        price = fv(det.get("stck_prpr", 0))

        if abs(prdy) > cfg["max_prdy"]:
            return 0, "관망", False, sigs, [
                f"❌ 당일 등락 {prdy:+.1f}% (허용 ±{cfg['max_prdy']}%)"]

        if w52l > 0 and price > 0:
            gap = (price - w52l) / w52l * 100
            if gap > cfg["from_52w"]:
                return 0, "관망", False, sigs, [
                    f"❌ 52주저점 대비 +{gap:.1f}% (허용 {cfg['from_52w']}%)"]
            s7 = round((1.0 - gap / cfg["from_52w"]) * 10, 1)
    sigs["SIG7_바닥권"] = s7

    # SIG-8: 거래량 폭발 + 필터 (10pt)
    s8 = 0
    if det:
        avol = iv(det.get("acml_vol", 0))
        mvol = iv(det.get("avrg_vol", 0))
        if mvol > 0:
            vr = avol / mvol
            if vr < cfg["min_vol"]:
                return 0, "관망", False, sigs, [
                    f"❌ 거래량 {vr:.2f}x < {cfg['min_vol']}x"]
            s8 = min(10.0, (vr - 1.0) * 4.0)
    sigs["SIG8_거래량"] = round(s8, 1)

    # SIG-9: 시간대 보정 (5pt)
    if cfg["time_filter"]:
        s9 = {"prime": 5, "normal": 2, "caution": 0, "closed": 0}.get(session, 0)
    else:
        s9 = 2
    sigs["SIG9_시간대"] = s9

    total = round(sum(sigs.values()), 1)

    if   total >= 70:                     grade = "S"
    elif total >= 55:                     grade = "A"
    elif total >= cfg["threshold"] * 10:  grade = "B"
    else:
        return 0, "관망", False, sigs, ["점수 기준 미달"]

    msgs = []
    if sigs["SIG1_수급강도"] >= 15: msgs.append(f"🔴 대규모 수급 {qty:,}주")
    if sigs["SIG2_기관동반"]:        msgs.append("🏦 기관 동반 매수")
    if sigs["SIG3_프로그램"]:        msgs.append("🔥 프로그램 동반")
    if sigs["SIG4_급등"]:            msgs.append(f"⚡ 매수강도 {sg:.1f}배 급등")
    if sigs["SIG5_연속매수"] >= 7:   msgs.append(f"📅 {consec}일 연속 외국인 매수")
    if sigs["SIG6_분봉방향"] == 10:  msgs.append("📈 분봉 연속 상승")
    if sigs["SIG7_바닥권"] >= 7:     msgs.append("📉 52주 바닥권 진입")
    if sigs["SIG8_거래량"] >= 7:     msgs.append("💥 거래량 폭발")
    if sigs["SIG9_시간대"] == 5:     msgs.append("⏰ 황금시간대")

    return total, grade, True, sigs, msgs


# ════════════════════════════════════════════════════════════
#  7. 매도 경보 점수 — 4개 시그널
# ════════════════════════════════════════════════════════════

def calc_sell_score(iscd, qty, prdy, det,
                    daily_hist, minute_bars):
    sigs = {}
    abs_qty = abs(min(qty, 0))

    # SIG-A: 수급 이탈 (35pt)
    sA = (35 if abs_qty>=1_000_000 else 28 if abs_qty>=500_000
          else 20 if abs_qty>=200_000 else 12 if abs_qty>=50_000
          else max(0, abs_qty / 50_000 * 12))
    sigs["SIGA_수급이탈"] = round(sA, 1)

    # SIG-B: 연속 순매도일 (20pt)
    cs = 0
    for day in daily_hist:
        if iv(day.get("frgn_ntby_qty", 0)) < 0: cs += 1
        else: break
    sigs["SIGB_연속매도"] = (20 if cs>=5 else 14 if cs>=3
                               else 8 if cs>=2 else 4 if cs>=1 else 0)

    # SIG-C: 고점권 + 분봉 하락 (25pt)
    sC = 0
    if det:
        w52h  = fv(det.get("w52_hgpr", 0))
        price = fv(det.get("stck_prpr", 0))
        if w52h > 0 and price > 0:
            from_h = (w52h - price) / w52h * 100
            if from_h < 10:
                sC += (1.0 - from_h / 10.0) * 15
    if len(minute_bars) >= 3:
        closes = [fv(b.get("stck_prpr", b.get("stck_clpr", 0)))
                  for b in minute_bars[:5]]
        closes = [c for c in closes if c > 0]
        if len(closes) >= 3:
            falling = sum(1 for i in range(1, len(closes))
                          if closes[i] < closes[i-1])
            if falling >= len(closes) - 1: sC += 10
            elif falling >= len(closes) // 2: sC += 5
    sigs["SIGC_고점분봉"] = round(min(25, sC), 1)

    # SIG-D: 거래량 감소 + 하락 (20pt)
    sD = 0
    if det:
        avol = iv(det.get("acml_vol", 0))
        mvol = iv(det.get("avrg_vol", 0))
        if mvol > 0:
            vr = avol / mvol
            if vr < 0.8 and prdy < 0:
                sD = min(20, (1.0 - vr) * 25)
    sigs["SIGD_거래량감소"] = round(sD, 1)

    total = round(sum(sigs.values()), 1)

    msgs = []
    if sigs["SIGA_수급이탈"] >= 20: msgs.append(f"🟣 대규모 순매도 {abs_qty:,}주")
    if sigs["SIGB_연속매도"] >= 8:  msgs.append(f"📅 {cs}일 연속 외국인 매도")
    if sigs["SIGC_고점분봉"] >= 15: msgs.append("⛰️ 52주 고점권 + 분봉 하락")
    if sigs["SIGD_거래량감소"] >= 10: msgs.append("📊 거래량 감소 + 하락")

    return total, sigs, msgs


# ════════════════════════════════════════════════════════════
#  8. 목표가 / 손절가
# ════════════════════════════════════════════════════════════

def calc_tp_sl(price: int, grade: str, cfg: dict):
    mult_tp = {"S": 1.6, "A": 1.2, "B": 0.8}.get(grade, 1.0)
    mult_sl = {"S": 0.8, "A": 1.0, "B": 1.2}.get(grade, 1.0)
    tp_pct  = cfg["tp"] * mult_tp
    sl_pct  = cfg["sl"] * mult_sl
    return (round(price * (1 + tp_pct / 100)),
            round(price * (1 - sl_pct / 100)),
            tp_pct, sl_pct)


# ════════════════════════════════════════════════════════════
#  9. 전체 파이프라인
# ════════════════════════════════════════════════════════════

def run_pipeline(token, app_key, app_secret, base_url,
                 cfg: dict) -> tuple[list, list, list]:
    session = market_session()

    print("  📡 [1/4] 외국인 순매수 수집 중...")
    frg = fetch_investor(token, app_key, app_secret, base_url, "FRG")

    print("  📡 [2/4] 기관 순매수 수집 중...")
    org = fetch_investor(token, app_key, app_secret, base_url, "ORG")

    print("  📡 [3/4] 프로그램 매매 수집 중...")
    prg = fetch_program(token, app_key, app_secret, base_url)

    print("  📡 [4/4] 거래량 순위 수집 중...")
    vol = fetch_vol_rank(token, app_key, app_secret, base_url)

    # 집합 구성
    org_set = {r.get("mksc_shrn_iscd", "").strip() for r in org
               if iv(r.get("orgn_ntby_qty", 0)) > 0}
    prg_set = {r.get("mksc_shrn_iscd", "").strip() for r in prg
               if iv(r.get("pgm_ntby_tr_pbmn", r.get("ntby_tr_pbmn", 0))) > 0}
    vol_set = {r.get("mksc_shrn_iscd", "").strip() for r in vol}

    # 외국인 정규화
    def norm(raw):
        out = []
        for row in raw:
            cd = row.get("mksc_shrn_iscd", "").strip()
            if not cd: continue
            qty = iv(row.get("frgn_ntby_qty", 0))
            amt = iv(row.get("frgn_ntby_tr_pbmn", 0))
            push_hist(cd, qty)
            out.append({
                "코드":   cd,
                "종목명": row.get("hts_kor_isnm", "").strip(),
                "시장":   row.get("_mkt", ""),
                "현재가": iv(row.get("stck_prpr", 0)),
                "등락률": fv(row.get("prdy_ctrt", 0)),
                "순매수량": qty,
                "거래대금(백만)": round(amt / 1_000_000, 1),
            })
        return out

    frg_list = norm(frg)
    frg_list.sort(key=lambda x: x["순매수량"], reverse=True)
    buy_cands  = [r for r in frg_list if r["순매수량"] > 0][:50]
    sell_cands = sorted([r for r in frg_list if r["순매수량"] < 0],
                        key=lambda x: x["순매수량"])[:30]

    # ── 매수 분석 ──────────────────────────────────────────
    print(f"\n  🔬 매수 분석 중 ({len(buy_cands)}종목)...")
    buy_ranks = []
    for idx, row in enumerate(buy_cands, 1):
        cd = row["코드"]
        print(f"    [{idx:02d}/{len(buy_cands)}] {row['종목명']:<14}", end=" ")

        det   = fetch_detail(token, app_key, app_secret, base_url, cd)
        time.sleep(0.04)
        daily = fetch_investor_daily(token, app_key, app_secret, base_url, cd)
        time.sleep(0.06)
        mins  = fetch_minute(token, app_key, app_secret, base_url, cd, 5)
        time.sleep(0.04)

        sc, grade, ok, sigs, msgs = calc_buy_score(
            cd, row["순매수량"], row["거래대금(백만)"],
            row["등락률"], det,
            cd in org_set, cd in prg_set, cd in vol_set,
            daily, mins, cfg, session)

        if not ok:
            print("✗ 필터 탈락")
            continue

        tp, sl, tp_pct, sl_pct = calc_tp_sl(row["현재가"], grade, cfg)
        print(f"★ {grade}등급 {sc:.0f}pt  목표:{tp:,}  손절:{sl:,}")

        buy_ranks.append({
            **row,
            "기관동반":    "O" if cd in org_set else "-",
            "프로그램":    "O" if cd in prg_set else "-",
            "거래량급증":  "O" if cd in vol_set else "-",
            "추천등급":    grade,
            "매수점수":    sc,
            "목표가":      tp,
            "목표수익률":  f"+{tp_pct:.1f}%",
            "손절가":      sl,
            "손절률":      f"-{sl_pct:.1f}%",
            "포착근거":    " | ".join(msgs),
        })

    buy_ranks.sort(key=lambda x: x["매수점수"], reverse=True)

    # ── 매도 분석 ──────────────────────────────────────────
    print(f"\n  🔬 매도 경보 분석 중 ({len(sell_cands)}종목)...")
    sell_ranks = []
    for idx, row in enumerate(sell_cands, 1):
        cd = row["코드"]
        print(f"    [{idx:02d}/{len(sell_cands)}] {row['종목명']:<14}", end=" ")

        det   = fetch_detail(token, app_key, app_secret, base_url, cd)
        time.sleep(0.04)
        daily = fetch_investor_daily(token, app_key, app_secret, base_url, cd)
        time.sleep(0.06)
        mins  = fetch_minute(token, app_key, app_secret, base_url, cd, 5)
        time.sleep(0.04)

        sc, sigs, msgs = calc_sell_score(
            cd, row["순매수량"], row["등락률"], det, daily, mins)

        if sc < 20:
            print(f"△ {sc:.0f}pt (기준 미달)")
            continue

        level = "🚨 강력매도" if sc >= 70 else "⚠️ 경보"
        print(f"{level} {sc:.0f}pt")

        sell_ranks.append({
            **row,
            "매도경보점수": sc,
            "경보레벨":     "강력매도" if sc >= 70 else "매도경보",
            "포착근거":     " | ".join(msgs),
        })

    sell_ranks.sort(key=lambda x: x["매도경보점수"], reverse=True)

    # 거래량 정리
    vol_list = [{
        "코드":   r.get("mksc_shrn_iscd", "").strip(),
        "종목명": r.get("hts_kor_isnm", "").strip(),
        "시장":   r.get("_mkt", ""),
        "현재가": iv(r.get("stck_prpr", 0)),
        "등락률": fv(r.get("prdy_ctrt", 0)),
        "거래량": iv(r.get("acml_vol", 0)),
        "거래량비율": fv(r.get("vol_inrt", 0)),
    } for r in vol if r.get("mksc_shrn_iscd", "").strip()]

    return buy_ranks, sell_ranks, vol_list


# ════════════════════════════════════════════════════════════
#  10. 터미널 출력
# ════════════════════════════════════════════════════════════

W = 90

def _bar(char="═"): print(char * W)

def _title(text):
    _bar()
    print(f"  {text}   [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    _bar()


def print_buy(data: list[dict]):
    _title("📈 매수 추천 종목 (9시그널 통합 점수)")
    if not data:
        print("  결과 없음")
        _bar(); return
    print(f"  {'#':>3}  {'종목명':<14}{'코드':>7}  {'시장':>6}  "
          f"{'현재가':>9}  {'등락':>7}  {'등급':>4}  {'점수':>6}  "
          f"{'목표가':>9}  {'손절가':>9}")
    _bar("─")
    for i, r in enumerate(data, 1):
        chg = f"{r['등락률']:+.2f}%"
        print(f"  {i:>3}  {r['종목명']:<14}{r['코드']:>7}  {r['시장']:>6}  "
              f"{r['현재가']:>9,}  {chg:>7}  {r['추천등급']:>4}  "
              f"{r['매수점수']:>6.1f}  "
              f"{r['목표가']:>9,}  {r['손절가']:>9,}")
        if r.get("포착근거"):
            print(f"         → {r['포착근거']}")
    _bar()


def print_sell(data: list[dict]):
    _title("📉 매도 경보 종목 (4시그널 통합 점수)")
    if not data:
        print("  현재 매도 경보 없음")
        _bar(); return
    print(f"  {'#':>3}  {'종목명':<14}{'코드':>7}  {'시장':>6}  "
          f"{'현재가':>9}  {'등락':>7}  {'경보레벨':>8}  {'점수':>6}")
    _bar("─")
    for i, r in enumerate(data, 1):
        chg = f"{r['등락률']:+.2f}%"
        icon = "🚨" if r["경보레벨"] == "강력매도" else "⚠️"
        print(f"  {i:>3}  {r['종목명']:<14}{r['코드']:>7}  {r['시장']:>6}  "
              f"{r['현재가']:>9,}  {chg:>7}  "
              f"{icon}{r['경보레벨']:>7}  {r['매도경보점수']:>6.1f}")
        if r.get("포착근거"):
            print(f"         → {r['포착근거']}")
    _bar()


def print_vol(data: list[dict], top=15):
    _title("🔥 거래량 급증 종목 TOP 15 (평균 대비)")
    if not data:
        print("  데이터 없음"); _bar(); return
    print(f"  {'#':>3}  {'종목명':<14}{'코드':>7}  {'시장':>6}  "
          f"{'현재가':>9}  {'등락':>7}  {'거래량비율':>10}")
    _bar("─")
    for i, r in enumerate(data[:top], 1):
        chg = f"{r['등락률']:+.2f}%"
        print(f"  {i:>3}  {r['종목명']:<14}{r['코드']:>7}  {r['시장']:>6}  "
              f"{r['현재가']:>9,}  {chg:>7}  {r['거래량비율']:>9.1f}x")
    _bar()


def print_summary(buy_ranks, sell_ranks, session):
    sess_map = {"prime":"🟢 황금시간대(09:00~10:30)",
                "normal":"🔵 장 중",
                "caution":"🟡 마감정리(14:30~)",
                "closed":"⚫ 장 외"}
    s_cnt = sum(1 for r in buy_ranks if r["추천등급"] == "S")
    a_cnt = sum(1 for r in buy_ranks if r["추천등급"] == "A")
    b_cnt = sum(1 for r in buy_ranks if r["추천등급"] == "B")

    _bar()
    print(f"  ★ 요약  |  {sess_map.get(session,'')}")
    _bar("─")
    print(f"  매수추천 S:{s_cnt}개  A:{a_cnt}개  B:{b_cnt}개  "
          f"| 매도경보 {len(sell_ranks)}개")
    if buy_ranks:
        top = buy_ranks[0]
        print(f"  최고점수: {top['종목명']} ({top['추천등급']}등급 {top['매수점수']:.0f}pt) "
              f"— 목표 {top['목표가']:,}원 / 손절 {top['손절가']:,}원")
    _bar()


# ════════════════════════════════════════════════════════════
#  11. CSV 저장
# ════════════════════════════════════════════════════════════

def save_csv(data: list[dict], label: str):
    if not data: return
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    path = f"smt_{label}_{ts}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"  💾 저장 → {path}")


# ════════════════════════════════════════════════════════════
#  12. 메인
# ════════════════════════════════════════════════════════════

def main():
    print()
    print("  " + "★" * 26)
    print("    💰 스마트 머니 트래커 v5.0")
    print("    KIS API 전용  ·  9시그널 통합 알고리즘")
    print("  " + "★" * 26 + "\n")

    # 인증
    app_key, app_secret, is_real, cfg = get_credentials()
    base_url = BASE_REAL if is_real else BASE_PAPER

    # 토큰
    try:
        token = get_access_token(app_key, app_secret, base_url)
    except Exception as e:
        print(f"  ❌ 토큰 발급 실패: {e}")
        sys.exit(1)

    # 장 시간대
    session = market_session()
    sess_map = {"prime": "🟢 황금시간대 — 수급 신뢰도 최고",
                "normal": "🔵 장 중 — 정상 수집",
                "caution": "🟡 마감 정리 시간대 — 노이즈 주의",
                "closed": "⚫ 장 외 시간 — 데이터 제한적"}
    print(f"  ⏰ 현재 장 상태: {sess_map.get(session, '')}\n")

    # 갱신 주기
    raw = input("  자동 갱신 주기 (초, 0=단발) [기본: 0] : ").strip()
    interval = int(raw) if raw.isdigit() else 0
    if interval > 0:
        print(f"  ℹ️  {interval}초마다 자동 갱신 (Ctrl+C 종료)")
        print(f"  ℹ️  매수강도 급등(SIG-4)은 2회차부터 의미 있음\n")

    run_count = 0
    try:
        while True:
            run_count += 1
            print(f"\n  {'─'*W}")
            print(f"  🔍 [{run_count}회차] 수집 시작 "
                  f"({datetime.now().strftime('%H:%M:%S')})")
            print(f"  {'─'*W}\n")

            buy_r, sell_r, vol_l = run_pipeline(
                token, app_key, app_secret, base_url, cfg)

            print()
            print_summary(buy_r, sell_r, session)
            print()
            print_buy(buy_r)
            print()
            print_sell(sell_r)
            print()
            print_vol(vol_l)

            # CSV 저장
            save_yn = input("\n  CSV 저장? [y/N] : ").strip().lower()
            if save_yn == "y":
                save_csv(buy_r,  "buy")
                save_csv(sell_r, "sell")
                save_csv(vol_l,  "vol")

            if interval == 0:
                break

            print(f"\n  ⏳ {interval}초 후 재조회... (Ctrl+C 종료)")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n  👋 종료합니다.")


if __name__ == "__main__":
    main()
