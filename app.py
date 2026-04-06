# ════════════════════════════════════════════════════════════
#  大戶思維投資導航系統 — Streamlit Cloud 版 v2.2
#  Module 1：成長動能篩選器（掃全市場熱門股）
#  Module 2-1：三大法人買賣超（只掃 M1 候選名單）
# ════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="🐋 大戶思維投資導航", page_icon="🐋",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
    .stApp{background-color:#0a0f1a;color:#c9d1d9;}
    h1,h2,h3{color:#f0e070!important;}
    .alert-red{background:#3a1010;border-left:4px solid #ff4444;padding:10px 14px;border-radius:4px;margin:6px 0;}
    .alert-yellow{background:#2a1f00;border-left:4px solid #f0a500;padding:10px 14px;border-radius:4px;margin:6px 0;}
    .alert-green{background:#0d2015;border-left:4px solid #56d364;padding:10px 14px;border-radius:4px;margin:6px 0;}
    .alert-blue{background:#0a1e30;border-left:4px solid #4a9eff;padding:10px 14px;border-radius:4px;margin:6px 0;}
    .alert-gold{background:#1a1000;border-left:4px solid #f0a500;padding:10px 14px;border-radius:4px;margin:6px 0;}
</style>""", unsafe_allow_html=True)

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

WATCHLIST = list(dict.fromkeys(s for s in [
    "2330","2317","2454","2382","2308","2303","2881","2882","2891","2886","2884","2885","2892","2883","2887",
    "1301","1303","1326","2002","2105","2207","2357","2379","2395","2408","2412","2474","2603","2609","2615",
    "2801","3008","3045","3711","4904","4938","5871","5876","5880","6505","6669","8046","9910","2823","2880",
    "2337","2344","2345","2376","2388","2449","2451","3034","3037","3081","3293","3443","3673","3680","3706",
    "4961","4966","6415","6446","6464","6533","6550","6770","8069","2367","2385","2356","2360","2362","2377",
    "2387","2392","2393","2397","2399","3017","3019","3105","3231","3532","4977","5269","6214","6239","6269",
    "6278","6285","6289","6443","6449","6510","6531","6547","1101","1102","1216","1402","1605","2027","2049",
    "2201","2204","2352","2371","2404","2849","3702","4912","5009","5274","6116","6176","9941","9945","1590",
    "2610","2618",
] if s.isdigit() and 4 <= len(s) <= 6))

def get_token():
    try: return st.secrets["FINMIND_TOKEN"]
    except: return ""

@st.cache_data(ttl=3600)
def fetch_stock_revenue(stock_id, start_date, token):
    try:
        r = requests.get(FINMIND_URL, params={"dataset":"TaiwanStockMonthRevenue",
            "data_id":stock_id,"start_date":start_date,"token":token}, timeout=10)
        data = r.json()
        if data.get("status") != 200: return pd.DataFrame()
        df = pd.DataFrame(data.get("data",[]))
        if df.empty: return df
        df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
        df["year_month"] = df.apply(lambda r: f"{int(r['revenue_year'])}-{int(r['revenue_month']):02d}", axis=1)
        return df[["stock_id","revenue","revenue_year","revenue_month","year_month"]]
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_stock_name(stock_id, token):
    try:
        r = requests.get(FINMIND_URL, params={"dataset":"TaiwanStockInfo","data_id":stock_id,"token":token}, timeout=8)
        data = r.json().get("data",[])
        if data: return data[0].get("stock_name","—")
    except: pass
    return "—"

@st.cache_data(ttl=3600)
def fetch_gross_margin(stock_id, token):
    try:
        r = requests.get(FINMIND_URL, params={"dataset":"TaiwanStockFinancialStatements",
            "data_id":stock_id,"start_date":"2023-01-01","token":token}, timeout=10)
        df = pd.DataFrame(r.json().get("data",[]))
        if df.empty: return None
        gp = df[df["type"]=="GrossProfit"]["value"].values
        rev = df[df["type"]=="Revenue"]["value"].values
        if len(gp)>0 and len(rev)>0 and float(rev[-1])!=0:
            return round(float(gp[-1])/float(rev[-1])*100,2)
    except: pass
    return None

def batch_revenue_scan(stock_list, start_date, token):
    bar = st.progress(0, text="📡 Module 1：掃描月營收...")
    frames = []
    for i,sid in enumerate(stock_list):
        df = fetch_stock_revenue(sid, start_date, token)
        if not df.empty: frames.append(df)
        bar.progress((i+1)/len(stock_list), text=f"📡 M1 掃描 {i+1}/{len(stock_list)}：{sid}")
        if (i+1)%10==0: time.sleep(0.3)
    bar.empty()
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def calc_yoy(df):
    df = df.sort_values(["stock_id","revenue_year","revenue_month"])
    df["revenue_last_year"] = df.groupby(["stock_id","revenue_month"])["revenue"].shift(1)
    df["yoy_pct"] = ((df["revenue"]-df["revenue_last_year"])/df["revenue_last_year"].abs()*100).round(2)
    return df.dropna(subset=["yoy_pct"])

def run_growth_scanner(df, min_yoy, min_slope, months_back, token):
    cutoff = (datetime.today()-timedelta(days=30*months_back)).strftime("%Y-%m")
    df = df[df["year_month"]>=cutoff].sort_values(["stock_id","year_month"])
    results = []
    for sid, grp in df.groupby("stock_id"):
        grp = grp.drop_duplicates("year_month").tail(6).reset_index(drop=True)
        if len(grp)<3 or grp["yoy_pct"].isna().sum()>2: continue
        yoy = grp["yoy_pct"].fillna(0).values
        slope = float(np.polyfit(range(len(yoy)), yoy, 1)[0])
        if not (all(v>min_yoy for v in yoy[-3:]) and slope>min_slope): continue
        results.append({"股票代號":str(sid),"公司名稱":"—","最新YoY(%)":round(float(yoy[-1]),1),
                        "加速斜率":round(slope,2),"連3月正成長":"✅","成長加速中":"✅"})
    out = pd.DataFrame(results)
    if out.empty: return out
    for idx,row in out.iterrows():
        out.at[idx,"公司名稱"] = fetch_stock_name(row["股票代號"], token)
        time.sleep(0.05)
    return out.sort_values("加速斜率", ascending=False).reset_index(drop=True)

def run_fake_detector(candidates, token, threshold):
    if candidates.empty: return candidates
    risks = []
    bar = st.progress(0, text="🔍 M1：毛利率偵測中...")
    total = min(len(candidates),20)
    for i,row in candidates.head(total).iterrows():
        m = fetch_gross_margin(str(row["股票代號"]), token)
        risks.append("—（無資料）" if m is None else f"⚠️ {m}%" if m<threshold else f"✅ {m}%")
        bar.progress((i+1)/total); time.sleep(0.1)
    bar.empty()
    result = candidates.head(total).copy()
    result["毛利率狀態"] = risks
    return result

@st.cache_data(ttl=1800)
def fetch_institutional(stock_id, start_date, token):
    try:
        r = requests.get(FINMIND_URL, params={"dataset":"TaiwanStockInstitutionalInvestorsBuySell",
            "data_id":stock_id,"start_date":start_date,"token":token}, timeout=10)
        data = r.json()
        if data.get("status")!=200: return pd.DataFrame()
        raw = pd.DataFrame(data.get("data",[]))
        if raw.empty: return pd.DataFrame()
        raw["date"] = pd.to_datetime(raw["date"])
        raw["buy"] = pd.to_numeric(raw.get("buy",0), errors="coerce").fillna(0)
        raw["sell"] = pd.to_numeric(raw.get("sell",0), errors="coerce").fillna(0)
        raw["net"] = raw["buy"] - raw["sell"]
        if "name" in raw.columns:
            pivot = raw.pivot_table(index=["date","stock_id"], columns="name",
                                    values="net", aggfunc="sum").reset_index()
            pivot.columns.name = None
            rename_map = {}
            for col in pivot.columns:
                c = str(col)
                if "外資" in c and "外資自行" not in c: rename_map[col]="外資買賣超"
                elif "投信" in c: rename_map[col]="投信買賣超"
                elif "自營" in c: rename_map[col]="自營買賣超"
            pivot = pivot.rename(columns=rename_map)
        else:
            pivot = raw.copy()
            cr = {}
            for c in pivot.columns:
                cs=str(c)
                if "Foreign" in cs and "Buy" in cs: cr[c]="_fi_buy"
                elif "Foreign" in cs and "Sell" in cs: cr[c]="_fi_sell"
                elif "Investment_Trust" in cs and "Buy" in cs: cr[c]="_it_buy"
                elif "Investment_Trust" in cs and "Sell" in cs: cr[c]="_it_sell"
                elif "Dealer" in cs and "Buy" in cs: cr[c]="_dl_buy"
                elif "Dealer" in cs and "Sell" in cs: cr[c]="_dl_sell"
            pivot = pivot.rename(columns=cr)
            for pf,oc in [("_fi","外資買賣超"),("_it","投信買賣超"),("_dl","自營買賣超")]:
                b,s=f"{pf}_buy",f"{pf}_sell"
                if b in pivot.columns and s in pivot.columns:
                    pivot[oc]=(pd.to_numeric(pivot[b],errors="coerce").fillna(0)-
                               pd.to_numeric(pivot[s],errors="coerce").fillna(0))
        for col in ["外資買賣超","投信買賣超","自營買賣超"]:
            if col not in pivot.columns: pivot[col]=0
            pivot[col]=pd.to_numeric(pivot[col],errors="coerce").fillna(0)/1000
        pivot["三大合計"]=pivot["外資買賣超"]+pivot["投信買賣超"]+pivot["自營買賣超"]
        pivot["stock_id"]=stock_id
        return pivot[["date","stock_id","外資買賣超","投信買賣超","自營買賣超","三大合計"]].sort_values("date")
    except: return pd.DataFrame()

def analyze_institutional(stock_id, df, days):
    if df.empty: return {}
    recent = df.tail(days)
    if len(recent)==0: return {}
    consec=0
    for v in reversed(recent["三大合計"].values):
        if v>0: consec+=1
        else: break
    buy_days=int((recent["三大合計"]>0).sum())
    total=len(recent)
    return {"stock_id":stock_id,"外資淨買(張)":round(recent["外資買賣超"].sum(),0),
            "投信淨買(張)":round(recent["投信買賣超"].sum(),0),
            "自營淨買(張)":round(recent["自營買賣超"].sum(),0),
            "三大合計(張)":round(recent["三大合計"].sum(),0),
            "連續買超天":consec,"買超天數":buy_days,"觀察天數":total,
            "買超比例":round(buy_days/total*100,1) if total>0 else 0}

def batch_institutional_scan(m1_candidates, start_date, token, min_consec, min_buy_ratio):
    """★ v2.2：只掃 M1 候選名單"""
    if m1_candidates.empty: return pd.DataFrame()
    m1_ids = m1_candidates["股票代號"].tolist()
    total = len(m1_ids)
    bar = st.progress(0, text=f"📊 Module 2：針對 M1 {total} 支候選掃描法人動向...")
    results = []
    for i,sid in enumerate(m1_ids):
        df = fetch_institutional(sid, start_date, token)
        if not df.empty:
            summary = analyze_institutional(sid, df, days=20)
            if summary:
                if summary["連續買超天"]>=min_consec or summary["買超比例"]>=min_buy_ratio:
                    results.append(summary)
        bar.progress((i+1)/total, text=f"📊 M2 法人追蹤 {i+1}/{total}：{sid}")
        time.sleep(0.2)
    bar.empty()
    if not results: return pd.DataFrame()
    out = pd.DataFrame(results)
    name_map = dict(zip(m1_candidates["股票代號"], m1_candidates["公司名稱"]))
    out.insert(1,"公司名稱",out["stock_id"].map(name_map).fillna("—"))
    def sl(row):
        if row["連續買超天"]>=5: return "🔥 強力買超"
        elif row["連續買超天"]>=3: return "✅ 持續買超"
        elif row["買超比例"]>=70: return "✅ 高頻買超"
        else: return "👀 值得觀察"
    out["信號強度"] = out.apply(sl, axis=1)
    return out.sort_values("連續買超天", ascending=False).reset_index(drop=True)

def cross_compare(m1_df, m2_df):
    if m1_df.empty or m2_df.empty: return pd.DataFrame()
    common = set(m1_df["股票代號"]) & set(m2_df["stock_id"])
    if not common: return pd.DataFrame()
    m1_sub = m1_df[m1_df["股票代號"].isin(common)].copy()
    m2_sub = m2_df[m2_df["stock_id"].isin(common)][
        ["stock_id","三大合計(張)","連續買超天","買超比例","信號強度"]
    ].rename(columns={"stock_id":"股票代號"})
    merged = m1_sub.merge(m2_sub, on="股票代號", how="inner")
    merged["綜合評分"] = (merged["加速斜率"]*0.5+merged["連續買超天"]*0.5).round(2)
    return merged.sort_values("綜合評分", ascending=False).reset_index(drop=True)

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🐋 大戶思維\n#### 投資導航系統 v2.2")
    st.divider()
    cloud_token = get_token()
    if cloud_token:
        st.success("✅ FinMind Token 已載入"); token_to_use = cloud_token
    else:
        st.markdown("#### 🔑 FinMind Token（必填）")
        token_to_use = st.text_input("貼上你的 Token", type="password", placeholder="finmindtrade.com 免費申請")
    st.divider()
    st.markdown("#### 📅 Module 1 設定")
    months_back = st.slider("回溯月數",3,6,5)
    min_yoy = st.number_input("最低 YoY 成長率 (%)",value=10.0,step=5.0)
    min_slope = st.number_input("最低加速斜率",value=0.0,step=0.5)
    margin_threshold = st.slider("毛利率警戒線 (%)",1,30,10)
    st.divider()
    st.markdown("#### 📊 Module 2 設定")
    st.markdown("<div style='background:#0d2015;border-left:3px solid #56d364;padding:8px 10px;border-radius:4px;font-size:11px;color:#8ba3b8;'>✅ v2.2：M2 只掃 M1 候選<br>省 Token・更快・更精準</div>", unsafe_allow_html=True)
    min_consec = st.slider("最低連續買超天數",1,10,1)
    min_buy_ratio = st.slider("最低買超比例 (%)",20,90,40)
    st.divider()
    st.markdown("#### 📋 自訂股票（選填）")
    custom_input = st.text_input("額外加入股票代號", placeholder="例：2330,6415")
    st.divider()
    st.markdown(f"<div style='font-size:11px;color:#8ba3b8;'>💡 Token 消耗預估<br>M1：約 {len(WATCHLIST)} 次<br>M2：約 10～20 次（僅候選）<br>合計：約 <strong style='color:#56d364;'>{len(WATCHLIST)+20} 次</strong></div>", unsafe_allow_html=True)
    st.divider()
    st.caption("資料來源：FinMind Open API")
    st.caption("本系統僅供研究參考，不構成投資建議")
    run_btn = st.button("🚀 開始分析", use_container_width=True, type="primary", disabled=not token_to_use)

# ── 主畫面 ────────────────────────────────────────────────────
st.title("🐋 大戶思維投資導航系統")
st.caption("Module 1 成長動能  ×  Module 2-1 三大法人  ｜  v2.2")

tab_cross, tab_m1, tab_m2, tab_guide, tab_road = st.tabs(
    ["🎯 交叉比對","📈 Module 1","📊 Module 2","📖 使用說明","🗺 開發路線圖"])

with tab_guide:
    st.markdown("""
### 📱 操作方式
1. 左側輸入 **FinMind Token**（必填）
2. 調整 M1、M2 參數
3. 按「🚀 開始分析」（約 2～3 分鐘）
4. 優先看「🎯 交叉比對」Tab

### 🔄 v2.2 雙重漏斗邏輯
M1 掃全部 122 支（業績篩選）→ 篩出候選 → M2 只掃這些候選（法人確認）→ 🎯 最終強力名單

### 📊 Module 2 欄位說明
| 欄位 | 說明 |
|------|------|
| **三大合計(張)** | 外資+投信+自營 近期淨買張數 |
| **連續買超天** | 連續幾個交易日法人合計買超 |
| **買超比例(%)** | 觀察期間買超天數佔比 |
| **信號強度** | 🔥強力 ✅持續 👀觀察 |

### 💡 建議使用節奏
- **每月 10 日後**：M1+M2 完整跑一次（找新候選）
- **每天**：只看 M2 Tab 監控法人動向（消耗極少 Token）
""")

with tab_road:
    st.markdown("""
### ✅ 已完成
- Module 1：成長動能篩選 + 做帳偵測
- Module 2-1：三大法人買賣超（雙重漏斗）
- M1 × M2 交叉比對

### 🔄 Module 2 規劃中
- Module 2-2：抗跌強勢偵測
- Module 2-3：發動點偵測

### 📅 後續
- Module 3：政策 NLP 分析
- Module 4：停損紀律控制台
""")

if not token_to_use:
    with tab_cross:
        st.markdown('<div class="alert-blue"><strong>🔑 請先在左側輸入 FinMind Token</strong><br>前往 <a href="https://finmindtrade.com" target="_blank">finmindtrade.com</a> 免費註冊。</div>', unsafe_allow_html=True)
elif not run_btn:
    with tab_cross:
        st.markdown('<div style="text-align:center;padding:60px 0;color:#506880;"><div style="font-size:56px">🐋</div><p style="font-size:18px;margin-top:16px;">Token 已就緒，按左側「開始分析」</p><p style="font-size:12px;">v2.2：M2 只掃 M1 候選，約 2～3 分鐘完成</p></div>', unsafe_allow_html=True)
else:
    scan_list = WATCHLIST.copy()
    if custom_input.strip():
        extras = [s.strip() for s in custom_input.split(",") if s.strip().isdigit() and 4<=len(s.strip())<=6]
        scan_list = list(dict.fromkeys(scan_list+extras))
    m1_start = (datetime.today()-timedelta(days=30*(months_back+13))).strftime("%Y-%m-%d")
    m2_start = (datetime.today()-timedelta(days=35)).strftime("%Y-%m-%d")

    with tab_m1:
        st.subheader("📈 Module 1 — 成長動能篩選")
        raw_df = batch_revenue_scan(scan_list, m1_start, token_to_use)
        if raw_df.empty: st.error("❌ 月營收資料抓取失敗。"); st.stop()
        yoy_df = calc_yoy(raw_df)
        m1_scanned = yoy_df["stock_id"].nunique()
        st.success(f"✅ 成功取得 {m1_scanned} 支股票營收資料")
        with st.spinner("⚙️ 執行成長動能篩選..."):
            m1_result = run_growth_scanner(yoy_df, min_yoy, min_slope, months_back, token_to_use)
        if not m1_result.empty:
            m1_result = run_fake_detector(m1_result, token_to_use, margin_threshold)
        c1,c2,c3,c4 = st.columns(4)
        m1_passed = len(m1_result)
        m1_flagged = (len(m1_result[m1_result["毛利率狀態"].str.contains("⚠️",na=False)])
                      if "毛利率狀態" in m1_result.columns else 0)
        c1.metric("掃描股票數",f"{m1_scanned}"); c2.metric("通過成長篩選",f"{m1_passed}")
        c3.metric("⚠️ 毛利率異常",f"{m1_flagged}"); c4.metric("✅ M1 最終候選",f"{m1_passed-m1_flagged}")
        if m1_result.empty:
            st.markdown('<div class="alert-yellow">無股票通過 M1 條件，請調低 YoY 門檻。</div>', unsafe_allow_html=True)
        else:
            d_cols = ["股票代號","公司名稱","最新YoY(%)","加速斜率","連3月正成長","成長加速中"]
            if "毛利率狀態" in m1_result.columns: d_cols.append("毛利率狀態")
            def hl(val):
                if "⚠️" in str(val): return "background:#3a1010;color:#ff6b6b"
                if "✅" in str(val): return "background:#0d2015;color:#56d364"
                return ""
            styled = (m1_result[d_cols].style.map(hl, subset=["毛利率狀態"] if "毛利率狀態" in d_cols else [])
                      .format({"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}"})
                      .background_gradient(subset=["加速斜率"], cmap="YlGn"))
            st.dataframe(styled, use_container_width=True, height=400)
            st.download_button("📥 下載 M1 CSV", data=m1_result[d_cols].to_csv(index=False,encoding="utf-8-sig"),
                file_name=f"m1_{datetime.today().strftime('%Y%m%d')}.csv", mime="text/csv")

    with tab_m2:
        st.subheader("📊 Module 2-1 — 三大法人買賣超")
        m1_count = len(m1_result) if 'm1_result' in dir() else 0
        st.markdown(f'<div class="alert-green">✅ v2.2：只針對 M1 篩出的 <strong>{m1_count} 支候選</strong>做法人追蹤</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="alert-blue">篩選條件：<strong>連續買超 ≥ {min_consec} 天</strong> 或 <strong>買超比例 ≥ {min_buy_ratio}%</strong></div>', unsafe_allow_html=True)
        if 'm1_result' not in dir() or m1_result.empty:
            st.warning("請先完成 Module 1 分析。")
        else:
            m2_result = batch_institutional_scan(m1_result, m2_start, token_to_use, min_consec, min_buy_ratio)
            if m2_result.empty:
                st.markdown('<div class="alert-yellow">M1 候選中目前無股票符合法人買超條件。<br>可試著降低門檻，或明天再試（FinMind 次數每日重置）。</div>', unsafe_allow_html=True)
            else:
                c1,c2,c3 = st.columns(3)
                strong = len(m2_result[m2_result["信號強度"].str.contains("🔥")])
                steady = len(m2_result[m2_result["信號強度"].str.contains("✅")])
                c1.metric("通過 M2 篩選",f"{len(m2_result)}"); c2.metric("🔥 強力買超",f"{strong}"); c3.metric("✅ 持續買超",f"{steady}")
                m2_cols = [c for c in ["stock_id","公司名稱","三大合計(張)","外資淨買(張)","投信淨買(張)","連續買超天","買超比例","信號強度"] if c in m2_result.columns]
                def hl2(val):
                    if "🔥" in str(val): return "background:#1a0d00;color:#f0a500"
                    if "✅" in str(val): return "background:#0d2015;color:#56d364"
                    if "👀" in str(val): return "background:#0a1e30;color:#4a9eff"
                    return ""
                styled2 = (m2_result[m2_cols].style.map(hl2, subset=["信號強度"])
                           .format({"買超比例":"{:.1f}%","三大合計(張)":"{:.0f}","外資淨買(張)":"{:.0f}","投信淨買(張)":"{:.0f}"})
                           .background_gradient(subset=["連續買超天"], cmap="YlGn"))
                st.dataframe(styled2, use_container_width=True, height=400)
                st.download_button("📥 下載 M2 CSV", data=m2_result[m2_cols].to_csv(index=False,encoding="utf-8-sig"),
                    file_name=f"m2_{datetime.today().strftime('%Y%m%d')}.csv", mime="text/csv")

    with tab_cross:
        st.subheader("🎯 交叉比對 — M1 × M2 最強訊號")
        st.markdown('<div class="alert-gold"><strong>業績加速成長（M1）＋ 三大法人持續買超（M2）= 雙重確認最強訊號</strong></div>', unsafe_allow_html=True)
        cross_result = pd.DataFrame()
        m1_ok = 'm1_result' in dir() and not m1_result.empty
        m2_ok = 'm2_result' in dir() and not m2_result.empty
        if m1_ok and m2_ok: cross_result = cross_compare(m1_result, m2_result)
        if not m1_ok:
            st.info("請先執行分析。")
        elif not m2_ok or cross_result.empty:
            st.markdown('<div class="alert-yellow">目前無股票同時通過 M1 和 M2。以下顯示 M1 業績候選名單供參考：</div>', unsafe_allow_html=True)
            if m1_ok:
                d_cols = ["股票代號","公司名稱","最新YoY(%)","加速斜率"]
                if "毛利率狀態" in m1_result.columns: d_cols.append("毛利率狀態")
                st.dataframe(m1_result[d_cols], use_container_width=True, height=320)
        else:
            st.markdown(f'<div class="alert-green">🎯 找到 <strong>{len(cross_result)}</strong> 支同時通過 M1 + M2 的標的！</div>', unsafe_allow_html=True)
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("M1 候選",f"{len(m1_result)}"); c2.metric("M2 通過",f"{len(m2_result)}")
            c3.metric("🎯 交叉命中",f"{len(cross_result)}"); c4.metric("最高綜合評分",f"{cross_result['綜合評分'].max():.2f}")
            st.divider()
            cross_cols = ["股票代號","公司名稱","最新YoY(%)","加速斜率","三大合計(張)","連續買超天","買超比例","信號強度","綜合評分"]
            if "毛利率狀態" in cross_result.columns: cross_cols.insert(4,"毛利率狀態")
            cross_cols = [c for c in cross_cols if c in cross_result.columns]
            def hl3(val):
                if "🔥" in str(val): return "background:#1a0d00;color:#f0a500"
                if "⚠️" in str(val): return "background:#3a1010;color:#ff6b6b"
                if "✅" in str(val): return "background:#0d2015;color:#56d364"
                if "👀" in str(val): return "background:#0a1e30;color:#4a9eff"
                return ""
            fmt = {"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}","三大合計(張)":"{:.0f}","買超比例":"{:.1f}%","綜合評分":"{:.2f}"}
            styled3 = (cross_result[cross_cols].style
                       .map(hl3, subset=[c for c in ["信號強度","毛利率狀態"] if c in cross_cols])
                       .format({k:v for k,v in fmt.items() if k in cross_cols})
                       .background_gradient(subset=["綜合評分"], cmap="YlOrRd"))
            st.dataframe(styled3, use_container_width=True, height=420)
            st.download_button("📥 下載交叉比對 CSV", data=cross_result[cross_cols].to_csv(index=False,encoding="utf-8-sig"),
                file_name=f"whale_cross_{datetime.today().strftime('%Y%m%d')}.csv", mime="text/csv")
            st.divider()
            st.markdown("#### 📋 各標的重點提示")
            for _,row in cross_result.iterrows():
                warn = "⚠️" in str(row.get("毛利率狀態",""))
                st.markdown(f'<div class="{"alert-red" if warn else "alert-green"}"><strong>{row["股票代號"]} {row["公司名稱"]}</strong> ｜ YoY <strong>{row["最新YoY(%)"]:.1f}%</strong> ｜ 連買 <strong>{int(row["連續買超天"])}</strong> 天 ｜ {row.get("信號強度","")}{"｜ ⚠️ 毛利率需注意" if warn else ""}</div>', unsafe_allow_html=True)
