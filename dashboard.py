"""
스마트 머니 트래커 v5.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
실행  : streamlit run dashboard.py
의존성: pip install streamlit requests pandas plotly openpyxl
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[v5.0 주요 강화]
- 한투 API만 사용 (외부 데이터 0개)
- 9개 알고리즘 시그널 통합 점수 (100점)
- 매수 진입 타이밍 로직 추가 (오전장/오후장 구분)
- 매도 타이밍 알림 (목표가/손절가 자동 계산)
- 종목 추적 수첩 (포착→결과 기록)
- 거래대금 기반 필터 (소형주 노이즈 제거)
"""

import time, math, io, json, collections
from datetime import datetime, date

import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ════════════════════════════════════════════════════════════
#  0. 페이지 설정
# ════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="스마트 머니 트래커 v5",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════════
#  1. CSS
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

:root{--bg:#080c14;--bg2:#0d1220;--bg3:#111a2c;--bd:#1a2d45;
      --tx:#c8d8ee;--mt:#4a6080;--bl:#3b82f6;--gn:#10b981;
      --rd:#ef4444;--or:#f59e0b;--pu:#8b5cf6;--cy:#06b6d4;}

html,body,.stApp{background:var(--bg)!important;color:var(--tx);font-family:'Noto Sans KR',sans-serif;}
.block-container{padding:1.1rem 1.6rem 2rem;max-width:100%!important;}

[data-testid="stSidebar"]{background:var(--bg2)!important;border-right:1px solid var(--bd);}
[data-testid="stSidebar"] *{color:var(--tx)!important;}

.stTextInput input{background:var(--bg3)!important;border:1px solid var(--bd)!important;
                   color:var(--tx)!important;border-radius:7px!important;font-size:.86rem!important;}
.stTextInput input:focus{border-color:var(--bl)!important;box-shadow:0 0 0 2px rgba(59,130,246,.2)!important;}
.stNumberInput input{background:var(--bg3)!important;border:1px solid var(--bd)!important;color:var(--tx)!important;border-radius:7px!important;}
.stSelectbox>div>div{background:var(--bg3)!important;border:1px solid var(--bd)!important;border-radius:7px!important;}

.stButton>button{background:linear-gradient(135deg,#1d4ed8,#0891b2);color:#fff;border:none;
                 border-radius:8px;font-weight:700;font-size:.9rem;padding:.55rem 1rem;
                 width:100%;transition:opacity .15s,transform .1s;letter-spacing:.03em;}
.stButton>button:hover{opacity:.82;transform:translateY(-1px);}

[data-testid="metric-container"]{background:var(--bg3);border:1px solid var(--bd);border-radius:10px;padding:.8rem 1rem;}
[data-testid="metric-container"] label{color:var(--mt)!important;font-size:.68rem!important;text-transform:uppercase;letter-spacing:.08em;}
[data-testid="stMetricValue"]{color:#f0f6ff!important;font-family:'JetBrains Mono',monospace!important;font-size:1.4rem!important;font-weight:700!important;}

[data-testid="stTabs"] button[role="tab"]{background:var(--bg3);border:1px solid var(--bd);
  border-bottom:none;border-radius:8px 8px 0 0;color:var(--mt);font-weight:600;font-size:.83rem;}
[data-testid="stTabs"] button[aria-selected="true"]{background:var(--bg2)!important;
  color:var(--bl)!important;border-color:var(--bl)!important;border-bottom:2px solid var(--bl)!important;}

.stDownloadButton>button{background:var(--bg3);color:var(--bl);border:1px solid var(--bd);
  border-radius:7px;font-size:.8rem;font-weight:600;padding:.38rem .85rem;}
.stDownloadButton>button:hover{background:var(--bd);}

[data-testid="stExpander"]{background:var(--bg3);border:1px solid var(--bd);border-radius:8px;}
.streamlit-expanderHeader{font-size:.84rem!important;}

/* 섹션 헤더 */
.sh{font-size:.93rem;font-weight:700;color:#e2e8f0;
    background:linear-gradient(90deg,#1a2d4a,transparent);
    border-left:3px solid var(--bl);padding:.4rem .85rem;
    border-radius:0 6px 6px 0;margin:.9rem 0 .45rem;letter-spacing:.03em;}
.sh-sell{border-left-color:var(--pu)!important;}
.sh-track{border-left-color:var(--gn)!important;}

/* 시그널 뱃지 */
.sig{display:inline-block;padding:2px 8px;border-radius:99px;font-size:.72rem;font-weight:700;margin:1px;}
.sig-on {background:#1a3a1a;color:#4ade80;border:1px solid var(--gn);}
.sig-off{background:#1a1a2a;color:#475569;border:1px solid #2a3040;}
.sig-warn{background:#2a1a0a;color:#fb923c;border:1px solid var(--or);}

/* 종목 카드 */
.sg{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:.65rem;margin-top:.4rem;}
.sc{background:var(--bg3);border:1px solid var(--bd);border-radius:10px;
    padding:.8rem .95rem;transition:border-color .15s,transform .1s;}
.sc:hover{border-color:var(--bl);transform:translateY(-2px);}
.sc-S{border-left:3px solid var(--rd);}
.sc-A{border-left:3px solid var(--or);}
.sc-B{border-left:3px solid var(--bl);}
.sc-sell{border-left:3px solid var(--pu);}
.sc-name{font-size:.88rem;font-weight:700;color:#e2e8f0;}
.sc-code{font-size:.7rem;color:var(--mt);font-family:'JetBrains Mono',monospace;}
.sc-price{font-family:'JetBrains Mono',monospace;font-size:1.02rem;font-weight:600;
          color:#f0f6ff;margin:.3rem 0 .15rem;}
.sc-bar-wrap{background:#1a2540;border-radius:99px;height:5px;margin:.35rem 0 .3rem;}
.sc-bar-buy {background:linear-gradient(90deg,#ef4444,#f59e0b);height:5px;border-radius:99px;}
.sc-bar-sell{background:linear-gradient(90deg,#8b5cf6,#3b82f6);height:5px;border-radius:99px;}
.sc-sigs{font-size:.7rem;line-height:1.9;margin-top:.3rem;}
.sc-tp{font-size:.72rem;color:#4ade80;margin-top:.25rem;}
.sc-sl{font-size:.72rem;color:#f87171;}

/* 추적 수첩 */
.track-card{background:var(--bg3);border:1px solid var(--bd);border-radius:8px;padding:.7rem .9rem;margin:.3rem 0;}
.track-win {border-left:3px solid var(--gn);}
.track-loss{border-left:3px solid var(--rd);}
.track-open{border-left:3px solid var(--or);}

.up  {color:#f87171;font-weight:700;}
.dn  {color:#34d399;font-weight:700;}
.flat{color:#94a3b8;}

/* 시간대 배너 */
.time-banner{border-radius:8px;padding:.5rem 1rem;font-size:.82rem;font-weight:600;margin-bottom:.7rem;text-align:center;}
.time-prime {background:#0f2a0f;border:1px solid var(--gn);color:#4ade80;}
.time-caution{background:#2a1a0a;border:1px solid var(--or);color:#fb923c;}
.time-closed{background:#1a1a2a;border:1px solid #2a3040;color:var(--mt);}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  2. 상수
# ════════════════════════════════════════════════════════════
BASE_REAL  = "https://openapi.koreainvestment.com:9443"
BASE_PAPER = "https://openapivts.koreainvestment.com:29443"
API_DELAY  = 0.08

# 매도 타이밍 기본값
DEFAULT_TP  = 5.0   # 목표 수익률 %
DEFAULT_SL  = 3.0   # 손절 %
DEFAULT_AMT = 500   # 최소 거래대금 필터 (백만원)


# ════════════════════════════════════════════════════════════
#  3. 세션 초기화
# ════════════════════════════════════════════════════════════
_DEF = {
    "app_key":"","app_secret":"","is_real":True,
    "token":None,"token_ts":0,
    "buy_ranks":[],"sell_ranks":[],"vol_list":[],
    "ntby_hist":{},"supply_ts":{},
    "tracker":[],   # 추적 수첩
    "last_run":None,"run_count":0,
    "cfg":{
        "surge":1.5,"dual_bonus":2.0,"max_prdy":3.0,
        "from_52w":30.0,"min_vol":1.5,"threshold":4.0,
        "min_amt":DEFAULT_AMT,"tp":DEFAULT_TP,"sl":DEFAULT_SL,
        "time_filter":True,
    },
}
for k,v in _DEF.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ════════════════════════════════════════════════════════════
#  4. 유틸
# ════════════════════════════════════════════════════════════
def fv(v,d=0.0):
    try:    return float(str(v).replace(",",""))
    except: return d

def iv(v,d=0):
    try:    return int(str(v).replace(",",""))
    except: return d

def to_csv(df):
    return df.to_csv(index=False,encoding="utf-8-sig").encode("utf-8-sig")

def to_excel(df):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as w:
        df.to_excel(w,index=False,sheet_name="데이터")
    return buf.getvalue()

def now_hms(): return datetime.now().strftime("%H:%M:%S")
def ts_fname(): return datetime.now().strftime("%Y%m%d_%H%M")
def today_str(): return date.today().strftime("%Y-%m-%d")

def market_session():
    """
    장 시간대 반환
    prime   = 09:00~10:30  (황금시간 — 수급 가장 신뢰)
    caution = 14:30~15:30  (마감 포지션 정리 — 노이즈)
    normal  = 그 외 장중
    closed  = 장 외
    """
    now = datetime.now()
    h,m = now.hour, now.minute
    total = h*60+m
    if now.weekday() >= 5: return "closed"
    if total < 540 or total >= 930: return "closed"
    if 540 <= total < 630: return "prime"
    if 870 <= total < 930: return "caution"
    return "normal"


# ════════════════════════════════════════════════════════════
#  5. KIS API 함수 (한투 전용)
# ════════════════════════════════════════════════════════════
def burl(): return BASE_REAL if st.session_state.is_real else BASE_PAPER

def get_token():
    ss=st.session_state
    if ss.token and time.time()-ss.token_ts<86000: return ss.token
    r=requests.post(f"{burl()}/oauth2/tokenP",
        json={"grant_type":"client_credentials","appkey":ss.app_key,"appsecret":ss.app_secret},
        timeout=10)
    r.raise_for_status()
    t=r.json().get("access_token")
    if not t: raise ValueError("토큰 발급 실패 — KEY/SECRET을 확인하세요.")
    ss.token=t; ss.token_ts=time.time()
    return t

def hdr(tr_id):
    ss=st.session_state
    return {"Content-Type":"application/json; charset=utf-8",
            "authorization":f"Bearer {ss.token}",
            "appkey":ss.app_key,"appsecret":ss.app_secret,
            "tr_id":tr_id,"custtype":"P"}

def ag(url,tr_id,params,retry=3):
    for n in range(1,retry+1):
        time.sleep(API_DELAY)
        try:
            r=requests.get(url,headers=hdr(tr_id),params=params,timeout=10)
            if r.status_code==429: time.sleep(2**n); continue
            r.raise_for_status()
            d=r.json()
            if d.get("rt_cd")!="0": return None
            return d
        except: time.sleep(1)
    return None

# ── 5-1. 외국인/기관 순매수 상위 ──────────────────────────
def fetch_investor(inv="FRG"):
    url=f"{burl()}/uapi/domestic-stock/v1/quotations/foreign-institution-total"
    code="1" if inv=="FRG" else "2"
    out=[]
    for mkt in ["J","Q"]:
        d=ag(url,"FHPST02060000",{
            "fid_cond_mrkt_div_code":mkt,"fid_cond_scr_div_code":"16448",
            "fid_input_iscd":"0000","fid_div_cls_code":"1",
            "fid_rank_sort_cls_code":"0","fid_input_cnt_1":"50",
            "fid_etc_cls_code":code})
        if d and d.get("output"):
            for row in d["output"]:
                row["_mkt"]="KOSPI" if mkt=="J" else "KOSDAQ"
                out.append(row)
        time.sleep(0.1)
    return out

# ── 5-2. 프로그램 매매 ─────────────────────────────────────
def fetch_program():
    url=f"{burl()}/uapi/domestic-stock/v1/quotations/program-trade-by-stock"
    out=[]
    for mkt in ["J","Q"]:
        d=ag(url,"FHPST01710000",{
            "fid_cond_mrkt_div_code":mkt,"fid_cond_scr_div_code":"20171",
            "fid_input_iscd":"0000","fid_div_cls_code":"0",
            "fid_rank_sort_cls_code":"0","fid_input_cnt_1":"50"})
        if d and d.get("output"):
            for row in d["output"]:
                row["_mkt"]="KOSPI" if mkt=="J" else "KOSDAQ"
                out.append(row)
        time.sleep(0.1)
    return out

# ── 5-3. 종목 기본 시세 + 52주 고저가 + 거래량 ─────────────
def fetch_detail(iscd):
    url=f"{burl()}/uapi/domestic-stock/v1/quotations/inquire-price"
    d=ag(url,"FHKST01010100",{"fid_cond_mrkt_div_code":"J","fid_input_iscd":iscd})
    return d.get("output") if d else None

# ── 5-4. 거래량 순위 ────────────────────────────────────────
def fetch_vol_rank():
    url=f"{burl()}/uapi/domestic-stock/v1/quotations/volume-rank"
    out=[]
    for mkt in ["J","Q"]:
        d=ag(url,"FHPST01050000",{
            "fid_cond_mrkt_div_code":mkt,"fid_cond_scr_div_code":"20171",
            "fid_input_iscd":"0000","fid_div_cls_code":"0","fid_blng_cls_code":"0",
            "fid_trgt_cls_code":"111111111","fid_trgt_exls_cls_code":"000000",
            "fid_input_price_1":"1000","fid_input_price_2":"999999",
            "fid_vol_cnt":"100000","fid_input_date_1":""})
        if d and d.get("output"):
            for row in d["output"]:
                row["_mkt"]="KOSPI" if mkt=="J" else "KOSDAQ"
                out.append(row)
        time.sleep(0.1)
    return out

# ── 5-5. 분봉 데이터 (매수 타이밍 판단용) ──────────────────
def fetch_minute(iscd, n=10):
    """
    최근 n개 분봉 — 단기 방향성 판단
    FHKST03010200 : 주식 당일 분봉
    """
    url=f"{burl()}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    now=datetime.now().strftime("%H%M%S")
    d=ag(url,"FHKST03010200",{
        "fid_etc_cls_code":"","fid_cond_mrkt_div_code":"J",
        "fid_input_iscd":iscd,"fid_input_hour_1":now,
        "fid_pw_data_incu_yn":"N"})
    if d and d.get("output2"):
        return d["output2"][:n]
    return []

# ── 5-6. 투자자별 일별 매매 동향 (연속 순매수일 체크) ──────
def fetch_investor_daily(iscd):
    """
    FHKST01010900 : 투자자별 일별 매매 동향
    외국인이 며칠 연속 매수하는지 확인
    """
    url=f"{burl()}/uapi/domestic-stock/v1/quotations/inquire-investor"
    d=ag(url,"FHKST01010900",{
        "fid_cond_mrkt_div_code":"J",
        "fid_input_iscd":iscd,
        "fid_input_date_1":"",
        "fid_input_date_2":"",
        "fid_period_div_code":"D"})
    if d and d.get("output"):
        return d["output"][:5]   # 최근 5거래일
    return []


# ════════════════════════════════════════════════════════════
#  6. 히스토리
# ════════════════════════════════════════════════════════════
def push_hist(iscd,qty):
    h=st.session_state.ntby_hist
    if iscd not in h: h[iscd]=collections.deque(maxlen=10)
    h[iscd].append(qty)
    sh=st.session_state.supply_ts
    if iscd not in sh: sh[iscd]=[]
    sh[iscd].append((now_hms(),qty))
    if len(sh[iscd])>20: sh[iscd]=sh[iscd][-20:]

def surge_ratio(iscd):
    h=st.session_state.ntby_hist.get(iscd)
    if not h or len(h)<2: return 1.0
    return h[-1]/max(abs(h[-2]),1)

def supply_trend_3(iscd):
    h=list(st.session_state.ntby_hist.get(iscd,[]))
    if len(h)<3: return 0.0
    return sum(h[i]-h[i-1] for i in range(1,len(h)))/(len(h)-1)


# ════════════════════════════════════════════════════════════
#  7. 핵심 알고리즘 — 9개 시그널
# ════════════════════════════════════════════════════════════
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
매수 점수 구성 (총 100점)

SIG-1  외국인 순매수 강도    20pt  수량 + 거래대금 기준
SIG-2  기관 동반 여부        10pt  외국인+기관 동시 매수
SIG-3  프로그램 동반 여부    10pt  외국인+프로그램 동시
SIG-4  매수강도 급등         15pt  직전 스냅샷 대비 증가율
SIG-5  연속 순매수일         10pt  3일 이상 연속 외국인 매수
SIG-6  분봉 방향성           10pt  최근 분봉 상승 추세
SIG-7  바닥권 위치           10pt  52주 저점 30% 이내
SIG-8  거래량 폭발           10pt  평균 대비 1.5배 이상
SIG-9  장 시간대 보정        5pt   황금시간대(09~10:30) 가산
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

def calc_buy_score(iscd, qty, amt_mil, prdy, det,
                   is_org, is_prg, is_vol,
                   daily_hist, minute_bars, cfg, session):
    sigs = {}   # 시그널별 점수 기록

    # ── SIG-1: 외국인 순매수 강도 (20pt) ──────────────────
    # 수량 기준 (10pt)
    if   qty>=1_000_000: s1q=10
    elif qty>=500_000:   s1q=8
    elif qty>=200_000:   s1q=6
    elif qty>=100_000:   s1q=4
    elif qty>=50_000:    s1q=2
    else:                s1q=0
    # 거래대금 기준 (10pt) — 소형주 노이즈 제거 핵심
    if   amt_mil>=5000:  s1a=10
    elif amt_mil>=2000:  s1a=8
    elif amt_mil>=1000:  s1a=6
    elif amt_mil>=500:   s1a=4
    elif amt_mil>=200:   s1a=2
    else:                s1a=0
    sigs["SIG1_수급강도"] = s1q+s1a

    # 거래대금 최소 필터
    if amt_mil < cfg["min_amt"]:
        return 0,"관망",False,sigs,[f"❌ 거래대금 {amt_mil:.0f}백만원 < 최소 {cfg['min_amt']}백만원"]

    # ── SIG-2: 기관 동반 (10pt) ───────────────────────────
    sigs["SIG2_기관동반"] = 10 if is_org else 0

    # ── SIG-3: 프로그램 동반 (10pt) ──────────────────────
    sigs["SIG3_프로그램"] = 10 if is_prg else 0

    # ── SIG-4: 매수강도 급등 (15pt) ───────────────────────
    sg = surge_ratio(iscd)
    if sg >= cfg["surge"]:
        sigs["SIG4_급등"] = round(min(15.0, math.log2(max(sg,1.001))*7.5), 1)
    else:
        sigs["SIG4_급등"] = 0

    # ── SIG-5: 연속 순매수일 (10pt) ───────────────────────
    consec = 0
    if daily_hist:
        for day in daily_hist:
            frg_qty = iv(day.get("frgn_ntby_qty", day.get("frgn_seln_qty",0)))
            if frg_qty > 0: consec += 1
            else: break
    if   consec >= 5: s5=10
    elif consec >= 3: s5=7
    elif consec >= 2: s5=4
    elif consec >= 1: s5=2
    else:             s5=0
    sigs["SIG5_연속매수"] = s5

    # ── SIG-6: 분봉 방향성 (10pt) ────────────────────────
    s6 = 0
    if minute_bars and len(minute_bars) >= 3:
        closes=[fv(b.get("stck_prpr",b.get("stck_clpr",0))) for b in minute_bars[:5]]
        closes=[c for c in closes if c>0]
        if len(closes)>=3:
            rising = sum(1 for i in range(1,len(closes)) if closes[i]>closes[i-1])
            if rising >= len(closes)-1: s6=10   # 거의 모두 상승
            elif rising >= len(closes)//2: s6=5
    sigs["SIG6_분봉방향"] = s6

    # ── SIG-7: 바닥권 위치 + 필터 (10pt) ─────────────────
    s7 = 0
    if det:
        w52l  = fv(det.get("w52_lwpr",0))
        price = fv(det.get("stck_prpr",0))

        # 필터: 당일 급등 제외
        if abs(prdy) > cfg["max_prdy"]:
            return 0,"관망",False,sigs,[f"❌ 당일 등락 {prdy:+.1f}% (허용 ±{cfg['max_prdy']}%)"]

        if w52l>0 and price>0:
            gap=(price-w52l)/w52l*100
            if gap > cfg["from_52w"]:
                return 0,"관망",False,sigs,[f"❌ 52주저점 대비 +{gap:.1f}% (허용 {cfg['from_52w']}% 이내)"]
            proximity=1.0-gap/cfg["from_52w"]
            s7=round(proximity*10,1)
    sigs["SIG7_바닥권"] = s7

    # ── SIG-8: 거래량 폭발 + 필터 (10pt) ─────────────────
    s8 = 0
    if det:
        avol=iv(det.get("acml_vol",0))
        mvol=iv(det.get("avrg_vol",0))
        if mvol>0:
            vr=avol/mvol
            if vr<cfg["min_vol"]:
                return 0,"관망",False,sigs,[f"❌ 거래량 {vr:.2f}x < 최소 {cfg['min_vol']}x"]
            s8=min(10.0,(vr-1.0)*4.0)
    sigs["SIG8_거래량"] = round(s8,1)

    # ── SIG-9: 시간대 보정 (5pt) ──────────────────────────
    if cfg["time_filter"]:
        if session=="prime":   s9=5
        elif session=="normal":s9=2
        elif session=="caution":s9=0
        else:                  s9=0
    else:
        s9=2   # 시간 필터 OFF시 중립값
    sigs["SIG9_시간대"] = s9

    # ── 총점 계산 ──────────────────────────────────────────
    total=round(sum(sigs.values()),1)

    if   total>=70: grade="S"
    elif total>=55: grade="A"
    elif total>=cfg["threshold"]*10: grade="B"
    else: return 0,"관망",False,sigs,["점수 기준 미달"]

    # 활성 시그널 목록
    sig_msgs=[]
    if sigs["SIG1_수급강도"]>=15: sig_msgs.append(f"🔴 대규모 수급 {qty:,}주")
    if sigs["SIG2_기관동반"]:     sig_msgs.append("🏦 기관 동반 매수")
    if sigs["SIG3_프로그램"]:     sig_msgs.append("🔥 프로그램 동반")
    if sigs["SIG4_급등"]:         sig_msgs.append(f"⚡ 매수강도 {sg:.1f}배 급등")
    if sigs["SIG5_연속매수"]>=7:  sig_msgs.append(f"📅 {consec}일 연속 외국인 매수")
    if sigs["SIG6_분봉방향"]==10: sig_msgs.append("📈 분봉 연속 상승")
    if sigs["SIG7_바닥권"]>=7:    sig_msgs.append("📉 52주 바닥권 진입")
    if sigs["SIG8_거래량"]>=7:    sig_msgs.append("💥 거래량 폭발")
    if sigs["SIG9_시간대"]==5:    sig_msgs.append("⏰ 황금시간대")

    return total, grade, True, sigs, sig_msgs


# ════════════════════════════════════════════════════════════
#  8. 매도 경보 알고리즘 (4개 시그널)
# ════════════════════════════════════════════════════════════
"""
SIG-A  수급 이탈 강도    35pt
SIG-B  연속 순매도일     20pt
SIG-C  고점권 + 분봉하락 25pt
SIG-D  거래량 감소+하락  20pt
"""
def calc_sell_score(iscd, qty, prdy, det, daily_hist, minute_bars):
    sigs={}

    # SIG-A: 수급 이탈 (35pt)
    abs_qty=abs(min(qty,0))
    if   abs_qty>=1_000_000: sA=35
    elif abs_qty>=500_000:   sA=28
    elif abs_qty>=200_000:   sA=20
    elif abs_qty>=50_000:    sA=12
    else:                    sA=max(0,abs_qty/50_000*12)
    sigs["SIGA_수급이탈"]=round(sA,1)

    # SIG-B: 연속 순매도일 (20pt)
    consec_sell=0
    if daily_hist:
        for day in daily_hist:
            frg=iv(day.get("frgn_ntby_qty",0))
            if frg<0: consec_sell+=1
            else: break
    if   consec_sell>=5: sB=20
    elif consec_sell>=3: sB=14
    elif consec_sell>=2: sB=8
    elif consec_sell>=1: sB=4
    else:                sB=0
    sigs["SIGB_연속매도"]=sB

    # SIG-C: 고점권 + 분봉 하락 (25pt)
    sC=0
    if det:
        w52h=fv(det.get("w52_hgpr",0))
        price=fv(det.get("stck_prpr",0))
        if w52h>0 and price>0:
            from_high=(w52h-price)/w52h*100
            if from_high<10:
                sC+=(1.0-from_high/10.0)*15
    if minute_bars and len(minute_bars)>=3:
        closes=[fv(b.get("stck_prpr",b.get("stck_clpr",0))) for b in minute_bars[:5]]
        closes=[c for c in closes if c>0]
        if len(closes)>=3:
            falling=sum(1 for i in range(1,len(closes)) if closes[i]<closes[i-1])
            if falling>=len(closes)-1: sC+=10
            elif falling>=len(closes)//2: sC+=5
    sigs["SIGC_고점분봉"]=round(min(25,sC),1)

    # SIG-D: 거래량 감소 + 하락 (20pt)
    sD=0
    if det:
        avol=iv(det.get("acml_vol",0))
        mvol=iv(det.get("avrg_vol",0))
        if mvol>0:
            vr=avol/mvol
            if vr<0.8 and prdy<0:
                sD=min(20,(1.0-vr)*25)
    sigs["SIGD_거래량감소"]=round(sD,1)

    total=round(sum(sigs.values()),1)

    msgs=[]
    if sigs["SIGA_수급이탈"]>=20: msgs.append(f"🟣 대규모 순매도 {abs_qty:,}주")
    if sigs["SIGB_연속매도"]>=8:  msgs.append(f"📅 {consec_sell}일 연속 외국인 매도")
    if sigs["SIGC_고점분봉"]>=15: msgs.append("⛰️ 52주 고점권 + 분봉 하락")
    if sigs["SIGD_거래량감소"]>=10: msgs.append("📊 거래량 감소 + 하락")

    return total, sigs, msgs


# ════════════════════════════════════════════════════════════
#  9. 목표가 / 손절가 계산
# ════════════════════════════════════════════════════════════
def calc_tp_sl(price, grade, cfg):
    """
    등급별 차등 목표가 설정
    S등급: 수익률 높게, 손절 좁게
    A등급: 중간
    B등급: 보수적
    """
    tp_mult = {"S":1.6,"A":1.2,"B":0.8}.get(grade,1.0)
    sl_mult = {"S":0.8,"A":1.0,"B":1.2}.get(grade,1.0)
    tp_pct  = cfg["tp"] * tp_mult
    sl_pct  = cfg["sl"] * sl_mult
    tp_price = round(price * (1 + tp_pct/100))
    sl_price = round(price * (1 - sl_pct/100))
    return tp_price, sl_price, tp_pct, sl_pct


# ════════════════════════════════════════════════════════════
#  10. 전체 파이프라인
# ════════════════════════════════════════════════════════════
def run_pipeline(cfg, log_fn):
    session = market_session()
    log_fn("🔐 토큰 확인 중...")
    get_token()

    log_fn("📡 외국인 순매수 수집 중...")
    frg = fetch_investor("FRG")
    log_fn("📡 기관 순매수 수집 중...")
    org = fetch_investor("ORG")
    log_fn("📡 프로그램 매매 수집 중...")
    prg = fetch_program()
    log_fn("📡 거래량 순위 수집 중...")
    vol = fetch_vol_rank()

    # 집합 구성
    org_set={r.get("mksc_shrn_iscd","").strip() for r in org
             if iv(r.get("orgn_ntby_qty",0))>0 and r.get("mksc_shrn_iscd","").strip()}
    prg_set={r.get("mksc_shrn_iscd","").strip() for r in prg
             if iv(r.get("pgm_ntby_tr_pbmn",r.get("ntby_tr_pbmn",0)))>0
             and r.get("mksc_shrn_iscd","").strip()}
    vol_set={r.get("mksc_shrn_iscd","").strip() for r in vol}

    # 외국인 정규화
    def norm_frg(raw):
        out=[]
        for row in raw:
            cd=row.get("mksc_shrn_iscd","").strip()
            if not cd: continue
            qty=iv(row.get("frgn_ntby_qty",0))
            amt=iv(row.get("frgn_ntby_tr_pbmn",0))
            push_hist(cd,qty)
            out.append({
                "코드":cd,"종목명":row.get("hts_kor_isnm","").strip(),
                "시장":row.get("_mkt",""),
                "현재가":iv(row.get("stck_prpr",0)),
                "등락률":fv(row.get("prdy_ctrt",0)),
                "순매수량":qty,
                "거래대금(백만)":round(amt/1_000_000,1),
            })
        return out

    frg_list=norm_frg(frg)
    frg_list.sort(key=lambda x:x["순매수량"],reverse=True)

    # 매수 후보: 순매수 상위 50
    buy_cands=[r for r in frg_list if r["순매수량"]>0][:50]
    # 매도 후보: 순매도 상위 30
    sell_cands=sorted([r for r in frg_list if r["순매수량"]<0],
                      key=lambda x:x["순매수량"])[:30]

    # ── 매수 분석 ──────────────────────────────────────────
    log_fn(f"🔬 매수 분석 중 ({len(buy_cands)}종목, 분봉+일별 포함)...")
    buy_ranks=[]
    for idx,row in enumerate(buy_cands,1):
        cd=row["코드"]
        log_fn(f"   [{idx}/{len(buy_cands)}] {row['종목명']} 분석 중...")

        det   = fetch_detail(cd); time.sleep(0.04)
        daily = fetch_investor_daily(cd); time.sleep(0.06)
        mins  = fetch_minute(cd,5); time.sleep(0.04)

        sc,grade,ok,sigs,msgs=calc_buy_score(
            cd, row["순매수량"], row["거래대금(백만)"],
            row["등락률"], det,
            cd in org_set, cd in prg_set, cd in vol_set,
            daily, mins, cfg, session)
        if not ok: continue

        tp,sl,tp_pct,sl_pct=calc_tp_sl(row["현재가"],grade,cfg)
        buy_ranks.append({**row,
            "기관동반":"O" if cd in org_set else "-",
            "프로그램":"🔥" if cd in prg_set else "-",
            "거래량급증":"💥" if cd in vol_set else "-",
            "추천등급":grade,"매수점수":sc,
            "목표가":tp,"목표수익률":f"+{tp_pct:.1f}%",
            "손절가":sl,"손절률":f"-{sl_pct:.1f}%",
            "시그널":sigs,"사유":"\n".join(msgs),
        })

    buy_ranks.sort(key=lambda x:x["매수점수"],reverse=True)

    # ── 매도 분석 ──────────────────────────────────────────
    log_fn(f"🔬 매도 경보 분석 중 ({len(sell_cands)}종목)...")
    sell_ranks=[]
    for idx,row in enumerate(sell_cands,1):
        cd=row["코드"]
        log_fn(f"   [{idx}/{len(sell_cands)}] {row['종목명']} 분석 중...")
        det   = fetch_detail(cd); time.sleep(0.04)
        daily = fetch_investor_daily(cd); time.sleep(0.06)
        mins  = fetch_minute(cd,5); time.sleep(0.04)
        sc,sigs,msgs=calc_sell_score(cd,row["순매수량"],row["등락률"],det,daily,mins)
        if sc<20: continue
        sell_ranks.append({**row,"매도경보점수":sc,"시그널":sigs,"사유":"\n".join(msgs)})

    sell_ranks.sort(key=lambda x:x["매도경보점수"],reverse=True)

    # 거래량 정리
    vol_list=[{
        "코드":r.get("mksc_shrn_iscd","").strip(),
        "종목명":r.get("hts_kor_isnm","").strip(),
        "시장":r.get("_mkt",""),
        "현재가":iv(r.get("stck_prpr",0)),
        "등락률":fv(r.get("prdy_ctrt",0)),
        "거래량":iv(r.get("acml_vol",0)),
        "거래량비율":fv(r.get("vol_inrt",0)),
    } for r in vol if r.get("mksc_shrn_iscd","").strip()]

    log_fn(f"✅ 완료! 매수추천 {len(buy_ranks)}개 · 매도경보 {len(sell_ranks)}개")
    return buy_ranks, sell_ranks, vol_list


# ════════════════════════════════════════════════════════════
#  11. 추적 수첩 (종목 포착 → 결과 기록)
# ════════════════════════════════════════════════════════════
def add_tracker(row):
    entry={
        "포착일":today_str(),
        "포착시각":now_hms(),
        "코드":row["코드"],
        "종목명":row["종목명"],
        "포착가":row["현재가"],
        "목표가":row.get("목표가",0),
        "손절가":row.get("손절가",0),
        "등급":row.get("추천등급",""),
        "점수":row.get("매수점수",0),
        "결과가":None,
        "결과률":None,
        "결과":None,   # WIN / LOSS / OPEN
    }
    st.session_state.tracker.append(entry)

def close_tracker(idx, result_price):
    t=st.session_state.tracker[idx]
    entry_p=t["포착가"]
    if entry_p and entry_p>0:
        pct=(result_price-entry_p)/entry_p*100
        t["결과가"]=result_price
        t["결과률"]=round(pct,2)
        t["결과"]="WIN" if pct>0 else "LOSS"
    st.session_state.tracker[idx]=t


# ════════════════════════════════════════════════════════════
#  12. 차트
# ════════════════════════════════════════════════════════════
DK=dict(paper_bgcolor="#080c14",plot_bgcolor="#0d1220",
        font=dict(family="Noto Sans KR",color="#c8d8ee"),
        margin=dict(l=50,r=20,t=38,b=40))

def chart_radar(sigs_dict, title=""):
    """시그널 레이더 차트"""
    cats=list(sigs_dict.keys())
    vals=list(sigs_dict.values())
    maxes={"SIG1_수급강도":20,"SIG2_기관동반":10,"SIG3_프로그램":10,
           "SIG4_급등":15,"SIG5_연속매수":10,"SIG6_분봉방향":10,
           "SIG7_바닥권":10,"SIG8_거래량":10,"SIG9_시간대":5}
    pcts=[v/maxes.get(k,10)*100 for k,v in zip(cats,vals)]
    labels=[k.split("_")[1] for k in cats]

    fig=go.Figure(go.Scatterpolar(
        r=pcts+[pcts[0]], theta=labels+[labels[0]],
        fill="toself", fillcolor="rgba(59,130,246,.15)",
        line=dict(color="#3b82f6",width=2),
        marker=dict(size=5,color="#3b82f6")))
    fig.update_layout(**DK,
        polar=dict(
            bgcolor="#111a2c",
            radialaxis=dict(visible=True,range=[0,100],
                            gridcolor="#1a2d45",tickcolor="#4a6080",
                            tickfont=dict(size=9)),
            angularaxis=dict(gridcolor="#1a2d45",tickcolor="#c8d8ee",
                             tickfont=dict(size=10))),
        showlegend=False,
        title=dict(text=title,font=dict(size=12,color="#60a5fa"),x=.02),
        height=300,margin=dict(l=40,r=40,t=40,b=40))
    return fig

def chart_buy_bar(buy_rows):
    if not buy_rows: return go.Figure()
    rows=buy_rows[:20]
    names=[r["종목명"] for r in rows]
    scores=[r["매수점수"] for r in rows]
    gc={"S":"#ef4444","A":"#f59e0b","B":"#3b82f6"}
    fig=go.Figure(go.Bar(
        x=scores,y=names,orientation="h",
        marker_color=[gc.get(r["추천등급"],"#3b82f6") for r in rows],
        text=[f"{s:.0f}pt ({r['추천등급']})" for s,r in zip(scores,rows)],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>점수: %{x:.0f}pt<extra></extra>"))
    fig.update_layout(**DK,
        title=dict(text="📊 매수 추천 점수 TOP 20",font=dict(size=12,color="#60a5fa"),x=.01),
        xaxis=dict(title="점수",gridcolor="#1a2d45",range=[0,115]),
        yaxis=dict(autorange="reversed",tickfont=dict(size=11)),
        height=max(280,30*len(rows)+60))
    return fig

def chart_sell_bar(sell_rows):
    if not sell_rows: return go.Figure()
    rows=sell_rows[:15]
    names=[r["종목명"] for r in rows]
    scores=[r["매도경보점수"] for r in rows]
    fig=go.Figure(go.Bar(
        x=scores,y=names,orientation="h",
        marker_color=["#8b5cf6" if s>=70 else "#6366f1" for s in scores],
        text=[f"{s:.0f}pt" for s in scores],textposition="outside",
        hovertemplate="<b>%{y}</b><br>경보: %{x:.0f}pt<extra></extra>"))
    fig.update_layout(**DK,
        title=dict(text="🔔 매도 경보 점수 TOP 15",font=dict(size=12,color="#a78bfa"),x=.01),
        xaxis=dict(title="경보점수",gridcolor="#1a2d45",range=[0,115]),
        yaxis=dict(autorange="reversed",tickfont=dict(size=11)),
        height=max(250,30*len(rows)+60))
    return fig

def chart_supply_trend():
    sh=st.session_state.supply_ts
    br=st.session_state.buy_ranks
    if not br: return go.Figure()
    import plotly.express as px
    colors=px.colors.qualitative.Plotly
    fig=go.Figure()
    drawn=0
    for idx,row in enumerate(br[:8]):
        cd=row["코드"]
        hist=sh.get(cd,[])
        if len(hist)<2: continue
        xs=[h[0] for h in hist]; ys=[h[1] for h in hist]
        fig.add_trace(go.Scatter(x=xs,y=ys,mode="lines+markers",name=row["종목명"],
            line=dict(width=2,color=colors[idx%len(colors)]),marker=dict(size=5),
            hovertemplate=f"<b>{row['종목명']}</b><br>%{{x}}<br>%{{y:,}}주<extra></extra>"))
        drawn+=1
    if not drawn:
        fig.add_annotation(text="2회 이상 조회 후 추이가 표시됩니다",
            xref="paper",yref="paper",x=.5,y=.5,showarrow=False,
            font=dict(size=13,color="#4a6080"))
    fig.update_layout(**DK,
        title=dict(text="📈 외국인 순매수 추이 (스냅샷별)",font=dict(size=12,color="#60a5fa"),x=.01),
        xaxis=dict(title="수집 시각",gridcolor="#1a2d45"),
        yaxis=dict(title="순매수량(주)",gridcolor="#1a2d45"),
        legend=dict(bgcolor="#0d1220",bordercolor="#1a2d45",borderwidth=1),
        hovermode="x unified",height=350)
    return fig

def chart_tracker_summary():
    tr=st.session_state.tracker
    if not tr: return go.Figure()
    wins  = sum(1 for t in tr if t["결과"]=="WIN")
    losses= sum(1 for t in tr if t["결과"]=="LOSS")
    opens = sum(1 for t in tr if t["결과"] is None)
    fig=go.Figure(go.Pie(
        labels=["수익","손실","미결"],values=[wins,losses,opens],
        marker_colors=["#10b981","#ef4444","#f59e0b"],
        hole=.55,textinfo="label+percent",
        hovertemplate="%{label}: %{value}건<extra></extra>"))
    closed=[t for t in tr if t["결과률"] is not None]
    avg=sum(t["결과률"] for t in closed)/len(closed) if closed else 0
    fig.add_annotation(text=f"평균\n{avg:+.1f}%",x=.5,y=.5,showarrow=False,
        font=dict(size=13,color="#f0f6ff",family="JetBrains Mono"))
    fig.update_layout(**DK,title=dict(text="📊 추적 수첩 성과",
        font=dict(size=12,color="#10b981"),x=.01),height=280,showlegend=True)
    return fig


# ════════════════════════════════════════════════════════════
#  13. 카드 렌더러
# ════════════════════════════════════════════════════════════
def sig_badges(sigs):
    labels={"SIG1_수급강도":"수급","SIG2_기관동반":"기관","SIG3_프로그램":"프로그램",
            "SIG4_급등":"급등","SIG5_연속매수":"연속매수","SIG6_분봉방향":"분봉↑",
            "SIG7_바닥권":"바닥권","SIG8_거래량":"거래량","SIG9_시간대":"황금시간"}
    maxes={"SIG1_수급강도":20,"SIG2_기관동반":10,"SIG3_프로그램":10,
           "SIG4_급등":15,"SIG5_연속매수":10,"SIG6_분봉방향":10,
           "SIG7_바닥권":10,"SIG8_거래량":10,"SIG9_시간대":5}
    parts=[]
    for k,lbl in labels.items():
        v=sigs.get(k,0)
        mx=maxes.get(k,10)
        if v>=mx*0.7:      cls="sig-on"
        elif v>=mx*0.3:    cls="sig-warn"
        else:              cls="sig-off"
        parts.append(f'<span class="sig {cls}">{lbl}</span>')
    return "".join(parts)

def render_buy_cards(rows, max_c=30):
    if not rows:
        st.info("현재 조건에 맞는 매수 추천 종목이 없습니다.")
        return
    gc_border={"S":"var(--rd)","A":"var(--or)","B":"var(--bl)"}
    html=['<div class="sg">']
    for r in rows[:max_c]:
        g=r["추천등급"]
        pc=r["현재가"]; pr=r["등락률"]
        prc="up" if pr>0 else "dn" if pr<0 else "flat"
        bar=min(100,int(r["매수점수"]))
        sigs_html=sig_badges(r.get("시그널",{}))
        rsn=r.get("사유","").replace("\n","<br>")
        tp=r.get("목표가",0); sl=r.get("손절가",0)
        tp_pct=r.get("목표수익률",""); sl_pct=r.get("손절률","")
        html.append(f"""
<div class="sc sc-{g}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div><div class="sc-name">{r['종목명']}</div>
         <div class="sc-code">{r['코드']} · {r['시장']}</div></div>
    <div style="text-align:right;">
      <span style="background:{'#3b0a0a' if g=='S' else '#2a1a00' if g=='A' else '#0a1a3a'};
        color:{'#f87171' if g=='S' else '#fbbf24' if g=='A' else '#60a5fa'};
        border:1px solid {'var(--rd)' if g=='S' else 'var(--or)' if g=='A' else 'var(--bl)'};
        padding:2px 8px;border-radius:99px;font-size:.72rem;font-weight:700;">{g}등급</span>
      <div style="font-size:.78rem;color:{'#f87171' if g=='S' else '#fbbf24' if g=='A' else '#60a5fa'};
        font-weight:700;margin-top:2px;">★{r['매수점수']:.0f}pt</div>
    </div>
  </div>
  <div class="sc-price">{pc:,}원 <span class="{prc}" style="font-size:.8rem;">{pr:+.2f}%</span></div>
  <div class="sc-bar-wrap"><div class="sc-bar-buy" style="width:{bar}%"></div></div>
  <div class="sc-sigs">{sigs_html}</div>
  <div class="sc-tp">🎯 목표가 {tp:,}원 ({tp_pct})</div>
  <div class="sc-sl">🛑 손절가 {sl:,}원 ({sl_pct})</div>
  <div style="font-size:.7rem;color:#4a6080;margin-top:.3rem;line-height:1.7;">{rsn}</div>
</div>""")
    html.append('</div>')
    st.markdown("".join(html),unsafe_allow_html=True)

def render_sell_cards(rows, max_c=20):
    if not rows:
        st.info("현재 매도 경보 종목이 없습니다.")
        return
    html=['<div class="sg">']
    for r in rows[:max_c]:
        sc=r["매도경보점수"]
        pc=r["현재가"]; pr=r["등락률"]
        prc="up" if pr>0 else "dn" if pr<0 else "flat"
        bar=min(100,int(sc))
        rsn=r.get("사유","").replace("\n","<br>")
        alert_lbl="🚨 강력매도" if sc>=70 else "⚠️ 매도경보"
        alert_c="#a78bfa" if sc>=70 else "#818cf8"
        html.append(f"""
<div class="sc sc-sell">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div><div class="sc-name">{r['종목명']}</div>
         <div class="sc-code">{r['코드']} · {r['시장']}</div></div>
    <span style="background:#1a0a2a;color:{alert_c};border:1px solid var(--pu);
      padding:2px 8px;border-radius:99px;font-size:.72rem;font-weight:700;">{alert_lbl}</span>
  </div>
  <div class="sc-price">{pc:,}원 <span class="{prc}" style="font-size:.8rem;">{pr:+.2f}%</span></div>
  <div class="sc-bar-wrap"><div class="sc-bar-sell" style="width:{bar}%"></div></div>
  <div style="font-size:.78rem;color:{alert_c};font-weight:700;margin:.25rem 0;">🔔 경보 {sc:.0f}점</div>
  <div style="font-size:.7rem;color:#4a6080;line-height:1.7;">{rsn}</div>
</div>""")
    html.append('</div>')
    st.markdown("".join(html),unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  14. 사이드바
# ════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 💰 스마트 머니 트래커")
    st.caption("v5.0  ·  KIS API 전용  ·  9시그널")
    st.divider()

    st.markdown("#### 🔑 API 키")
    with st.expander("KEY 입력 / 변경", expanded=not bool(st.session_state.app_key)):
        ak=st.text_input("APP KEY",    value=st.session_state.app_key,    type="password",key="inp_ak")
        sk=st.text_input("APP SECRET", value=st.session_state.app_secret, type="password",key="inp_sk")
        rl=st.toggle("실전투자 계좌", value=st.session_state.is_real,key="inp_rl")
        if st.button("💾 저장",key="save_key"):
            st.session_state.app_key=ak; st.session_state.app_secret=sk
            st.session_state.is_real=rl; st.session_state.token=None
            st.success("✅ 저장 완료")
    st.caption("🔒 키는 세션 메모리에만 보관됩니다")
    st.divider()

    st.markdown("#### ⚙️ 분석 설정")
    with st.expander("필터 / 목표가 조정"):
        cfg=st.session_state.cfg
        st.markdown("**수급 필터**")
        cfg["min_amt"]   =st.number_input("최소 거래대금 (백만원)",100,10000,int(cfg["min_amt"]),100)
        cfg["min_vol"]   =st.slider("최소 거래량 배수",1.0,5.0,cfg["min_vol"],0.1)
        cfg["max_prdy"]  =st.slider("등락률 상한 (%)",1.0,10.0,cfg["max_prdy"],0.5)
        cfg["from_52w"]  =st.slider("52주저점 대비 상한 (%)",5.0,60.0,cfg["from_52w"],5.0)
        cfg["surge"]     =st.slider("매수강도 급등 배수",1.0,5.0,cfg["surge"],0.1)
        cfg["threshold"] =st.slider("최소 점수 기준 (×10)",1.0,8.0,cfg["threshold"],0.5)
        st.markdown("**매도 타이밍**")
        cfg["tp"]        =st.slider("목표 수익률 (%)",1.0,20.0,cfg["tp"],0.5)
        cfg["sl"]        =st.slider("손절 기준 (%)",1.0,10.0,cfg["sl"],0.5)
        cfg["time_filter"]=st.toggle("황금시간대 가산점",value=cfg["time_filter"])
        st.session_state.cfg=cfg
    st.divider()

    run_btn=st.button("▶  지금 조회하기",key="run_main")

    # 장 시간대 표시
    sess=market_session()
    if   sess=="prime":   st.markdown('<div class="time-banner time-prime">⏰ 황금시간대 (09:00~10:30)</div>',unsafe_allow_html=True)
    elif sess=="caution": st.markdown('<div class="time-banner time-caution">⚠️ 마감 정리 시간대 (14:30~)</div>',unsafe_allow_html=True)
    elif sess=="normal":  st.markdown('<div class="time-banner time-prime" style="border-color:var(--bl);color:#60a5fa;">📡 장 중</div>',unsafe_allow_html=True)
    else:                 st.markdown('<div class="time-banner time-closed">🔒 장 외 시간</div>',unsafe_allow_html=True)

    if st.session_state.last_run:
        st.caption(f"마지막: **{st.session_state.last_run}**")
        st.caption(f"누적 {st.session_state.run_count}회 조회")
    st.divider()
    st.markdown("[KIS Developers →](https://apiportal.koreainvestment.com)")


# ════════════════════════════════════════════════════════════
#  15. 메인 헤더
# ════════════════════════════════════════════════════════════
st.markdown("""
<div style="background:linear-gradient(135deg,#0d1829,#0e1c38,#0d1622);
     border:1px solid #1a2d45;border-radius:14px;padding:1.2rem 1.6rem;margin-bottom:1rem;">
  <div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;">
    <span style="font-size:1.8rem;">💰</span>
    <div>
      <div style="font-size:1.45rem;font-weight:900;color:#f0f6ff;letter-spacing:.02em;">
        스마트 머니 트래커
        <span style="font-size:.78rem;font-weight:400;color:#4a6a8a;margin-left:.4rem;">v5.0</span>
      </div>
      <div style="font-size:.8rem;color:#5a7898;margin-top:.18rem;">
        한국투자증권 KIS API 전용  ·  9개 시그널 통합 점수  ·
        분봉+연속매수일+거래대금 기반 알고리즘  ·  목표가/손절가 자동 계산
      </div>
    </div>
  </div>
</div>
""",unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  16. 조회 실행
# ════════════════════════════════════════════════════════════
log_area=st.empty()

if run_btn:
    if not st.session_state.app_key or not st.session_state.app_secret:
        st.error("⚠️ 사이드바에서 APP KEY / APP SECRET을 입력하고 저장해주세요.")
    else:
        prog=st.progress(0,"준비 중...")
        step=[0]; total_steps=20
        def log_fn(msg):
            step[0]+=1
            prog.progress(min(step[0]/total_steps,1.0),text=msg)
        try:
            buy_r,sell_r,vol_l=run_pipeline(st.session_state.cfg,log_fn)
            st.session_state.buy_ranks=buy_r
            st.session_state.sell_ranks=sell_r
            st.session_state.vol_list=vol_l
            st.session_state.last_run=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.run_count+=1
            prog.empty(); st.rerun()
        except Exception as e:
            prog.empty()
            st.error(f"❌ 오류: {e}")
            st.info("• APP KEY/SECRET 확인\n• 실전/모의 계좌 구분 확인\n• 장 운영 시간(09:00~15:30) 확인")


# ════════════════════════════════════════════════════════════
#  17. 데이터 없을 때 안내
# ════════════════════════════════════════════════════════════
buy_ranks  = st.session_state.buy_ranks
sell_ranks = st.session_state.sell_ranks
vol_list   = st.session_state.get("vol_list",[])

if not buy_ranks and not sell_ranks:
    st.markdown("""
    <div style="text-align:center;padding:3rem 2rem;color:#3a5060;
         border:1px dashed #1a2d45;border-radius:12px;margin-top:.5rem;">
      <div style="font-size:3rem;">📡</div>
      <div style="font-size:1rem;margin-top:.8rem;color:#4a6a8a;line-height:2;">
        <b style="color:#3b82f6;">① 사이드바</b>에서 APP KEY / SECRET 입력 후 저장<br>
        <b style="color:#3b82f6;">② ▶ 지금 조회하기</b> 클릭
      </div>
      <div style="font-size:.78rem;margin-top:.6rem;color:#2a3d50;">
        장 운영: 평일 09:00~15:30  ·  실전/모의 계좌 모두 지원
      </div>
    </div>
    """,unsafe_allow_html=True)
    st.stop()


# ════════════════════════════════════════════════════════════
#  18. 요약 지표
# ════════════════════════════════════════════════════════════
s_cnt=sum(1 for r in buy_ranks if r["추천등급"]=="S")
a_cnt=sum(1 for r in buy_ranks if r["추천등급"]=="A")
dual_cnt=sum(1 for r in buy_ranks if r.get("프로그램")=="🔥")
top_sc=buy_ranks[0]["매수점수"] if buy_ranks else 0
top_sell=sell_ranks[0]["매도경보점수"] if sell_ranks else 0
sess=market_session()
sess_label={"prime":"🟢 황금시간대","caution":"🟡 마감 시간대","normal":"🔵 장 중","closed":"⚫ 장 외"}.get(sess,"")

m1,m2,m3,m4,m5,m6=st.columns(6)
m1.metric("🔴 S등급 매수",f"{s_cnt}개")
m2.metric("🟡 A등급 매수",f"{a_cnt}개")
m3.metric("🔥 동반매수",f"{dual_cnt}개")
m4.metric("🏆 최고 점수",f"{top_sc:.0f}pt")
m5.metric("🔔 매도 경보",f"{len(sell_ranks)}개",delta=f"최고 {top_sell:.0f}pt" if sell_ranks else None)
m6.metric("⏰ 장 시간대",sess_label)


# ════════════════════════════════════════════════════════════
#  19. 탭
# ════════════════════════════════════════════════════════════
tab_buy, tab_sell, tab_detail, tab_trend, tab_track, tab_dl = st.tabs([
    "📈 매수 추천",
    "📉 매도 경보",
    "🔬 시그널 상세",
    "🔄 수급 추이",
    "📓 추적 수첩",
    "📥 다운로드",
])


# ── 탭: 매수 추천 ────────────────────────────────────────
with tab_buy:
    st.markdown('<div class="sh">📈 매수 추천 종목</div>',unsafe_allow_html=True)
    with st.expander("📖 9개 시그널 점수표"):
        st.markdown(f"""
| 시그널 | 최대 | 기준 |
|--------|------|------|
| SIG-1 외국인 수급강도 | 20pt | 순매수량 + 거래대금 {cfg['min_amt']}백만원 이상 |
| SIG-2 기관 동반 | 10pt | 기관도 동시 순매수 |
| SIG-3 프로그램 동반 | 10pt | 프로그램 동시 순매수 |
| SIG-4 매수강도 급등 | 15pt | 직전 대비 {cfg['surge']}배 이상 증가 |
| SIG-5 연속 순매수일 | 10pt | 외국인 3일+ 연속 매수 |
| SIG-6 분봉 방향성 | 10pt | 최근 5분봉 상승 추세 |
| SIG-7 바닥권 위치 | 10pt | 52주저점 {cfg['from_52w']}% 이내 |
| SIG-8 거래량 폭발 | 10pt | 평균 대비 {cfg['min_vol']}배 이상 |
| SIG-9 황금시간대 | 5pt | 09:00~10:30 수집 시 가산 |

**등급:** 🔴 S(70pt+) · 🟡 A(55pt+) · 🔵 B({int(cfg['threshold']*10)}pt+)
""")

    gc_f=st.multiselect("등급 필터",["S","A","B"],default=["S","A","B"],key="gf")
    filtered=[r for r in buy_ranks if r["추천등급"] in gc_f]

    col_bar,col_s=st.columns([3,2])
    with col_bar:
        st.plotly_chart(chart_buy_bar(buy_ranks),use_container_width=True)
    with col_s:
        st.markdown('<div class="sh" style="font-size:.85rem;">🔴 S등급 종목</div>',unsafe_allow_html=True)
        s_rows=[r for r in buy_ranks if r["추천등급"]=="S"]
        if s_rows: render_buy_cards(s_rows,6)
        else: st.caption("현재 S등급 없음")

    st.markdown('<div class="sh">전체 카드</div>',unsafe_allow_html=True)
    render_buy_cards(filtered,30)

    with st.expander("📋 테이블로 보기"):
        if buy_ranks:
            df_b=pd.DataFrame(buy_ranks).drop(columns=["시그널","사유"],errors="ignore")
            st.dataframe(df_b,use_container_width=True,hide_index=True)

        # 추적 수첩에 추가 버튼
        if buy_ranks:
            st.markdown("---")
            st.markdown("**추적 수첩에 추가**")
            sel=st.selectbox("종목 선택",
                [f"{r['종목명']} ({r['코드']}) — {r['추천등급']}등급 {r['매수점수']:.0f}pt"
                 for r in buy_ranks],key="sel_track")
            if st.button("📓 추적 수첩에 등록",key="add_track"):
                idx=next((i for i,r in enumerate(buy_ranks)
                          if r["코드"] in sel),None)
                if idx is not None:
                    add_tracker(buy_ranks[idx])
                    st.success("✅ 추적 수첩에 등록되었습니다!")


# ── 탭: 매도 경보 ────────────────────────────────────────
with tab_sell:
    st.markdown('<div class="sh sh-sell">📉 매도 경보 종목</div>',unsafe_allow_html=True)
    with st.expander("📖 매도 경보 시그널"):
        st.markdown("""
| 시그널 | 최대 | 기준 |
|--------|------|------|
| SIG-A 수급 이탈 강도 | 35pt | 외국인 순매도 규모 |
| SIG-B 연속 순매도일 | 20pt | 3일+ 연속 외국인 매도 |
| SIG-C 고점권+분봉하락 | 25pt | 52주 고점 10% 이내 + 분봉 하락 |
| SIG-D 거래량감소+하락 | 20pt | 거래량 줄며 주가 하락 |

**🚨 강력매도 70pt+ · ⚠️ 매도경보 20pt+**
""")

    col_sb,col_ss=st.columns([3,2])
    with col_sb:
        st.plotly_chart(chart_sell_bar(sell_ranks),use_container_width=True)
    with col_ss:
        st.markdown('<div class="sh sh-sell" style="font-size:.85rem;">🚨 강력 매도 경보</div>',unsafe_allow_html=True)
        strong=[r for r in sell_ranks if r["매도경보점수"]>=70]
        if strong: render_sell_cards(strong,6)
        else: st.caption("현재 강력 매도 경보 없음")

    st.markdown('<div class="sh sh-sell">전체 매도 경보 카드</div>',unsafe_allow_html=True)
    render_sell_cards(sell_ranks,20)

    with st.expander("📋 테이블로 보기"):
        if sell_ranks:
            df_s=pd.DataFrame(sell_ranks).drop(columns=["시그널","사유"],errors="ignore")
            st.dataframe(df_s,use_container_width=True,hide_index=True)


# ── 탭: 시그널 상세 ──────────────────────────────────────
with tab_detail:
    st.markdown('<div class="sh">🔬 종목별 9시그널 레이더 분석</div>',unsafe_allow_html=True)
    if not buy_ranks:
        st.info("조회 후 확인할 수 있습니다.")
    else:
        sel_name=st.selectbox("종목 선택",
            [f"{r['종목명']} — {r['추천등급']}등급 {r['매수점수']:.0f}pt" for r in buy_ranks],
            key="sel_radar")
        sel_idx=next((i for i,r in enumerate(buy_ranks)
                      if r["종목명"] in sel_name),0)
        sel_row=buy_ranks[sel_idx]

        c1,c2=st.columns([1,1])
        with c1:
            st.plotly_chart(
                chart_radar(sel_row.get("시그널",{}),f"{sel_row['종목명']} 시그널 레이더"),
                use_container_width=True)
        with c2:
            st.markdown(f"""
<div style="background:var(--bg3);border:1px solid var(--bd);border-radius:10px;padding:1rem 1.1rem;margin-top:.5rem;">
  <div style="font-size:1.05rem;font-weight:700;color:#f0f6ff;margin-bottom:.6rem;">{sel_row['종목명']}</div>
  <table style="width:100%;font-size:.82rem;border-collapse:collapse;">
    <tr><td style="color:var(--mt);padding:3px 0;">현재가</td>
        <td style="font-family:'JetBrains Mono',monospace;color:#f0f6ff;text-align:right;">{sel_row['현재가']:,}원</td></tr>
    <tr><td style="color:var(--mt);padding:3px 0;">추천등급</td>
        <td style="color:{'#f87171' if sel_row['추천등급']=='S' else '#fbbf24' if sel_row['추천등급']=='A' else '#60a5fa'};font-weight:700;text-align:right;">{sel_row['추천등급']}등급</td></tr>
    <tr><td style="color:var(--mt);padding:3px 0;">매수점수</td>
        <td style="font-family:'JetBrains Mono',monospace;color:#f0f6ff;text-align:right;">{sel_row['매수점수']:.1f}pt</td></tr>
    <tr><td style="color:var(--mt);padding:3px 0;">🎯 목표가</td>
        <td style="color:#4ade80;font-weight:700;text-align:right;">{sel_row.get('목표가',0):,}원 ({sel_row.get('목표수익률','')})</td></tr>
    <tr><td style="color:var(--mt);padding:3px 0;">🛑 손절가</td>
        <td style="color:#f87171;font-weight:700;text-align:right;">{sel_row.get('손절가',0):,}원 ({sel_row.get('손절률','')})</td></tr>
    <tr><td style="color:var(--mt);padding:3px 0;">기관동반</td>
        <td style="text-align:right;">{sel_row.get('기관동반','-')}</td></tr>
    <tr><td style="color:var(--mt);padding:3px 0;">프로그램</td>
        <td style="text-align:right;">{sel_row.get('프로그램','-')}</td></tr>
  </table>
</div>
""",unsafe_allow_html=True)

        # 시그널 점수 상세 테이블
        st.markdown('<div class="sh" style="font-size:.85rem;">시그널별 점수 상세</div>',unsafe_allow_html=True)
        sigs=sel_row.get("시그널",{})
        maxes={"SIG1_수급강도":20,"SIG2_기관동반":10,"SIG3_프로그램":10,
               "SIG4_급등":15,"SIG5_연속매수":10,"SIG6_분봉방향":10,
               "SIG7_바닥권":10,"SIG8_거래량":10,"SIG9_시간대":5}
        sig_rows=[]
        for k,v in sigs.items():
            mx=maxes.get(k,10)
            bar_pct=int(v/mx*100)
            bar_html=(f'<div style="background:#1a2540;border-radius:3px;height:8px;">'
                      f'<div style="background:{"#ef4444" if bar_pct>=70 else "#f59e0b" if bar_pct>=40 else "#3b82f6"};'
                      f'width:{bar_pct}%;height:8px;border-radius:3px;"></div></div>')
            sig_rows.append({"시그널":k.split("_")[1],"점수":v,"만점":mx,"달성률":f"{bar_pct}%"})
        df_sig=pd.DataFrame(sig_rows)
        st.dataframe(df_sig,use_container_width=True,hide_index=True)

        st.markdown("**포착 근거**")
        for line in sel_row.get("사유","없음").split("\n"):
            if line.strip(): st.markdown(f"- {line.strip()}")


# ── 탭: 수급 추이 ────────────────────────────────────────
with tab_trend:
    st.markdown('<div class="sh">🔄 외국인 순매수 추이</div>',unsafe_allow_html=True)
    if st.session_state.run_count<2:
        st.info("📡 **2회 이상 조회** 후 추이 그래프가 활성화됩니다.")
    else:
        st.plotly_chart(chart_supply_trend(),use_container_width=True)
        sh=st.session_state.supply_ts
        st.markdown('<div class="sh" style="font-size:.85rem;">종목별 미니 스파크라인</div>',unsafe_allow_html=True)
        cols=st.columns(4)
        drawn=0
        for idx,row in enumerate(buy_ranks[:8]):
            cd=row["코드"]
            hist=sh.get(cd,[])
            if len(hist)<2: continue
            ys=[h[1] for h in hist]
            mf=go.Figure(go.Scatter(y=ys,mode="lines+markers",
                line=dict(color="#3b82f6",width=2),marker=dict(size=4),
                fill="tozeroy",fillcolor="rgba(59,130,246,.06)"))
            mf.update_layout(**DK,
                title=dict(text=row["종목명"],font=dict(size=10,color="#4a6a8a"),x=.04),
                margin=dict(l=5,r=5,t=24,b=5),height=95,
                xaxis=dict(visible=False),yaxis=dict(visible=False),showlegend=False)
            cols[drawn%4].plotly_chart(mf,use_container_width=True)
            drawn+=1


# ── 탭: 추적 수첩 ────────────────────────────────────────
with tab_track:
    st.markdown('<div class="sh sh-track">📓 추적 수첩 — 포착 종목 성과 기록</div>',unsafe_allow_html=True)
    st.caption("매수 추천 탭의 테이블 하단에서 종목을 등록하면 여기서 결과를 기록할 수 있습니다.")

    tracker=st.session_state.tracker

    if not tracker:
        st.info("아직 추적 중인 종목이 없습니다.\n\n매수 추천 탭 → 테이블로 보기 → 추적 수첩에 등록")
    else:
        # 성과 요약
        closed=[t for t in tracker if t["결과률"] is not None]
        wins=  [t for t in closed if t["결과"]=="WIN"]
        losses=[t for t in closed if t["결과"]=="LOSS"]
        opens= [t for t in tracker if t["결과"] is None]
        avg_r= sum(t["결과률"] for t in closed)/len(closed) if closed else 0
        wr=    len(wins)/len(closed)*100 if closed else 0

        mc1,mc2,mc3,mc4=st.columns(4)
        mc1.metric("📊 전체 등록",f"{len(tracker)}건")
        mc2.metric("✅ 수익",f"{len(wins)}건")
        mc3.metric("❌ 손실",f"{len(losses)}건")
        mc4.metric("📈 평균 수익률",f"{avg_r:+.2f}%",delta=f"승률 {wr:.0f}%")

        if closed:
            st.plotly_chart(chart_tracker_summary(),use_container_width=True)

        st.markdown('<div class="sh sh-track" style="font-size:.85rem;">기록 목록</div>',unsafe_allow_html=True)

        for idx,t in enumerate(tracker):
            res=t.get("결과")
            cls="track-win" if res=="WIN" else "track-loss" if res=="LOSS" else "track-open"
            icon="✅" if res=="WIN" else "❌" if res=="LOSS" else "⏳"
            pct_txt=f"{t['결과률']:+.2f}%" if t["결과률"] is not None else "미결"
            pct_c="#4ade80" if res=="WIN" else "#f87171" if res=="LOSS" else "#f59e0b"

            st.markdown(f"""
<div class="track-card {cls}">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.3rem;">
    <div>
      <span style="font-size:.9rem;font-weight:700;color:#e2e8f0;">{icon} {t['종목명']}</span>
      <span style="font-size:.72rem;color:var(--mt);margin-left:.4rem;">{t['코드']} · {t['등급']}등급 {t['점수']:.0f}pt</span>
    </div>
    <span style="font-size:.9rem;font-weight:700;color:{pct_c};">{pct_txt}</span>
  </div>
  <div style="font-size:.75rem;color:var(--mt);margin-top:.3rem;line-height:1.8;">
    포착: {t['포착일']} {t['포착시각']} · 포착가: {t['포착가']:,}원 ·
    목표: {t.get('목표가',0):,}원 · 손절: {t.get('손절가',0):,}원
    {f"· 결과가: {t['결과가']:,}원" if t.get('결과가') else ""}
  </div>
</div>
""",unsafe_allow_html=True)

            # 결과 입력 (미결 건만)
            if res is None:
                with st.expander(f"결과 입력 — {t['종목명']}",expanded=False):
                    rp=st.number_input("결과 매도가 (원)",
                        min_value=1, value=int(t["포착가"]),
                        key=f"rp_{idx}_{t['코드']}")
                    if st.button(f"✅ 결과 기록",key=f"close_{idx}"):
                        close_tracker(idx,rp)
                        st.success("기록 완료!")
                        st.rerun()

        if st.button("🗑️ 전체 초기화",key="clear_track"):
            st.session_state.tracker=[]
            st.rerun()


# ── 탭: 다운로드 ─────────────────────────────────────────
with tab_dl:
    st.markdown('<div class="sh">📥 데이터 다운로드</div>',unsafe_allow_html=True)
    ts=ts_fname()

    def dl_row(title,df,label):
        if df is None or df.empty:
            st.caption(f"{title} — 데이터 없음"); st.divider(); return
        st.markdown(f"**{title}** ({len(df)}행)")
        c1,c2,_=st.columns([1,1,4])
        c1.download_button("📥 CSV",data=to_csv(df),
            file_name=f"{label}_{ts}.csv",mime="text/csv",
            use_container_width=True,key=f"csv_{label}")
        c2.download_button("📥 엑셀",data=to_excel(df),
            file_name=f"{label}_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,key=f"xl_{label}")
        st.divider()

    dl_row("📈 매수 추천",
           pd.DataFrame(buy_ranks).drop(columns=["시그널","사유"],errors="ignore")
           if buy_ranks else pd.DataFrame(),"buy_rank")
    dl_row("📉 매도 경보",
           pd.DataFrame(sell_ranks).drop(columns=["시그널","사유"],errors="ignore")
           if sell_ranks else pd.DataFrame(),"sell_rank")
    dl_row("🔥 거래량 급증",
           pd.DataFrame(vol_list) if vol_list else pd.DataFrame(),"vol_surge")
    dl_row("📓 추적 수첩",
           pd.DataFrame(tracker) if tracker else pd.DataFrame(),"tracker")
