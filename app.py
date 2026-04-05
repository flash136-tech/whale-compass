# ════════════════════════════════════════════════════════════
#  大戶思維投資導航系統 — Streamlit Cloud 版 v2.0
#  Module 1：成長動能篩選器
#  Module 2-1：三大法人買賣超追蹤
#  交叉比對：M1 × M2 強力候選名單
# ════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import time

st.set_page_config(
    page_title="🐋 大戶思維投資導航",
    page_icon="🐋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0a0f1a; color: #c9d1d9; }
    h1, h2, h3 { color: #f0e070 !important; }
    .alert-red {
        background: #3a1010; border-left: 4px solid #ff4444;
        padding: 10px 14px; border-radius: 4px; margin: 6px 0;
    }
    .alert-yellow {
        background: #2a1f00; border-left: 4px solid #f0a500;
        padding: 10px 14px; border-radius: 4px; margin: 6px 0;
    }
    .alert-green {
        background: #0d2015; border-left: 4px solid #56d364;
        padding: 10px 14px; border-radius: 4px; margin: 6px 0;
    }
    .alert-blue {
        background: #0a1e30; border-left: 4px solid #4a9eff;
        padding: 10px 14px; border-radius: 4px; margin: 6px 0;
    }
    .alert-gold {
        background: #1a1000; border-left: 4px solid #f0a500;
        padding: 10px 14px; border-radius: 4px; margin: 6px 0;
    }
</style>
""", unsafe_allow_html=True)

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

# ════════════════════════════════════════════════════════════
#  熱門股清單
# ════════════════════════════════════════════════════════════

WATCHLIST = [
    "2330","2317","2454","2382","2308","2303","2881","2882","2891",
    "2886","2884","2885","2892","2883","2887","1301","1303","1326",
    "2002","2105","2207","2357","2379","2395","2408","2412","2474",
    "2603","2609","2615","2801","3008","3045","3711","4904","4938",
    "5871","5876","5880","6505","6669","8046","9910","2823","2880",
    "2337","2344","2345","2376","2388","2449","2451","3034","3037",
    "3081","3293","3443","3673","3680","3706","4961","4966","6415",
    "6446","6464","6533","6550","6770","8069","2367","2385",
    "2356","2360","2362","2377","2387","2392","2393","2397","2399",
    "3017","3019","3105","3231","3532","4977","5269","6214","6239",
    "6269","6278","6285","6289","6443","6449","6510","6531","6547",
    "1101","1102","1216","1402","1605","2027","2049","2201",
    "2204","2352","2371","2404","2849","3702","4912","5009",
    "5274","6116","6176","9941","9945","1590","2610","2618",
]
WATCHLIST = list(dict.fromkeys(
    s for s in WATCHLIST if s.isdigit() and 4 <= len(s) <= 6
))


# ════════════════════════════════════════════════════════════
#  Token
# ════════════════════════════════════════════════════════════

def get_token() -> str:
    try:
        return st.secrets["FINMIND_TOKEN"]
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════
#  MODULE 1：月營收資料
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def fetch_stock_revenue(stock_id: str, start_date: str, token: str) -> pd.DataFrame:
    params = {
        "dataset":    "TaiwanStockMonthRevenue",
        "data_id":    stock_id,
        "start_date": start_date,
        "token":      token,
    }
    try:
        r    = requests.get(FINMIND_URL, params=params, timeout=10)
        data = r.json()
        if data.get("status") != 200:
            return pd.DataFrame()
        df = pd.DataFrame(data.get("data", []))
        if df.empty:
            return df
        df["revenue"]    = pd.to_numeric(df["revenue"], errors="coerce")
        df["year_month"] = df.apply(
            lambda r: f"{int(r['revenue_year'])}-{int(r['revenue_month']):02d}", axis=1
        )
        return df[["stock_id","revenue","revenue_year","revenue_month","year_month"]]
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_stock_name(stock_id: str, token: str) -> str:
    try:
        r    = requests.get(FINMIND_URL,
                            params={"dataset":"TaiwanStockInfo","data_id":stock_id,"token":token},
                            timeout=8)
        data = r.json().get("data", [])
        if data:
            return data[0].get("stock_name", "—")
    except Exception:
        pass
    return "—"


@st.cache_data(ttl=3600)
def fetch_gross_margin(stock_id: str, token: str):
    params = {
        "dataset":    "TaiwanStockFinancialStatements",
        "data_id":    stock_id,
        "start_date": "2023-01-01",
        "token":      token,
    }
    try:
        r  = requests.get(FINMIND_URL, params=params, timeout=10)
        df = pd.DataFrame(r.json().get("data", []))
        if df.empty:
            return None
        gp  = df[df["type"] == "GrossProfit"]["value"].values
        rev = df[df["type"] == "Revenue"]["value"].values
        if len(gp) > 0 and len(rev) > 0 and float(rev[-1]) != 0:
            return round(float(gp[-1]) / float(rev[-1]) * 100, 2)
    except Exception:
        pass
    return None


def batch_revenue_scan(stock_list, start_date, token):
    bar    = st.progress(0, text="📡 Module 1：掃描月營收...")
    total  = len(stock_list)
    frames = []
    for i, sid in enumerate(stock_list):
        df = fetch_stock_revenue(sid, start_date, token)
        if not df.empty:
            frames.append(df)
        bar.progress((i+1)/total, text=f"📡 M1 掃描 {i+1}/{total}：{sid}")
        if (i+1) % 10 == 0:
            time.sleep(0.3)
    bar.empty()
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def calc_yoy(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["stock_id","revenue_year","revenue_month"])
    df["revenue_last_year"] = df.groupby(
        ["stock_id","revenue_month"]
    )["revenue"].shift(1)
    df["yoy_pct"] = (
        (df["revenue"] - df["revenue_last_year"])
        / df["revenue_last_year"].abs() * 100
    ).round(2)
    return df.dropna(subset=["yoy_pct"])


def run_growth_scanner(df, min_yoy, min_slope, months_back, token):
    cutoff = (datetime.today() - timedelta(days=30*months_back)).strftime("%Y-%m")
    df     = df[df["year_month"] >= cutoff].sort_values(["stock_id","year_month"])
    results = []
    for sid, grp in df.groupby("stock_id"):
        grp = grp.drop_duplicates("year_month").tail(6).reset_index(drop=True)
        if len(grp) < 3 or grp["yoy_pct"].isna().sum() > 2:
            continue
        yoy   = grp["yoy_pct"].fillna(0).values
        slope = float(np.polyfit(range(len(yoy)), yoy, 1)[0])
        l3ok  = bool(all(v > min_yoy for v in yoy[-3:]))
        accel = slope > min_slope
        if not (l3ok and accel):
            continue
        results.append({
            "股票代號":   str(sid),
            "公司名稱":   "—",
            "最新YoY(%)": round(float(yoy[-1]), 1),
            "加速斜率":   round(slope, 2),
            "連3月正成長":"✅",
            "成長加速中": "✅",
        })
    out = pd.DataFrame(results)
    if out.empty:
        return out
    # 補名稱
    for idx, row in out.iterrows():
        out.at[idx, "公司名稱"] = fetch_stock_name(row["股票代號"], token)
        time.sleep(0.05)
    return out.sort_values("加速斜率", ascending=False).reset_index(drop=True)


def run_fake_detector(candidates, token, threshold):
    if candidates.empty:
        return candidates
    risks = []
    bar   = st.progress(0, text="🔍 M1：毛利率偵測中...")
    total = min(len(candidates), 20)
    for i, row in candidates.head(total).iterrows():
        m = fetch_gross_margin(str(row["股票代號"]), token)
        risks.append(
            "—（無資料）" if m is None else
            f"⚠️ {m}%" if m < threshold else f"✅ {m}%"
        )
        bar.progress((i+1)/total)
        time.sleep(0.1)
    bar.empty()
    result = candidates.head(total).copy()
    result["毛利率狀態"] = risks
    return result


# ════════════════════════════════════════════════════════════
#  MODULE 2-1：三大法人買賣超
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800)
def fetch_institutional(stock_id: str, start_date: str, token: str) -> pd.DataFrame:
    """
    抓取三大法人每日買賣超資料
    dataset: TaiwanStockInstitutionalInvestorsBuySell
    欄位：Foreign_Investor（外資）, Investment_Trust（投信）, Dealer（自營商）
    """
    params = {
        "dataset":    "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id":    stock_id,
        "start_date": start_date,
        "token":      token,
    }
    try:
        r    = requests.get(FINMIND_URL, params=params, timeout=10)
        data = r.json()
        if data.get("status") != 200:
            return pd.DataFrame()
        df = pd.DataFrame(data.get("data", []))
        if df.empty:
            return df

        # 整理欄位
        df["date"] = pd.to_datetime(df["date"])
        num_cols = ["Foreign_Investor_Buy","Foreign_Investor_Sell",
                    "Investment_Trust_Buy","Investment_Trust_Sell",
                    "Dealer_Buy","Dealer_Sell"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # 計算各法人買賣超（買 - 賣，單位：張）
        if "Foreign_Investor_Buy" in df.columns:
            df["外資買賣超"] = (df["Foreign_Investor_Buy"] - df["Foreign_Investor_Sell"]) / 1000
        if "Investment_Trust_Buy" in df.columns:
            df["投信買賣超"] = (df["Investment_Trust_Buy"] - df["Investment_Trust_Sell"]) / 1000
        if "Dealer_Buy" in df.columns:
            df["自營買賣超"] = (df["Dealer_Buy"] - df["Dealer_Sell"]) / 1000

        df["三大合計"] = (
            df.get("外資買賣超", 0) +
            df.get("投信買賣超", 0) +
            df.get("自營買賣超", 0)
        )
        df["stock_id"] = stock_id
        return df[["date","stock_id","外資買賣超","投信買賣超","自營買賣超","三大合計"]].sort_values("date")

    except Exception:
        return pd.DataFrame()


def analyze_institutional(stock_id: str, df: pd.DataFrame, days: int) -> dict:
    """
    分析最近 N 天的三大法人行為，回傳摘要指標
    """
    if df.empty:
        return {}
    recent = df.tail(days)
    total  = len(recent)
    if total == 0:
        return {}

    foreign_net  = recent["外資買賣超"].sum()
    trust_net    = recent["投信買賣超"].sum()
    dealer_net   = recent["自營買賣超"].sum()
    combined_net = recent["三大合計"].sum()

    # 連續買超天數（從最近一天往前數）
    consec = 0
    for v in reversed(recent["三大合計"].values):
        if v > 0:
            consec += 1
        else:
            break

    # 買超天數比例
    buy_days = int((recent["三大合計"] > 0).sum())

    return {
        "stock_id":   stock_id,
        "外資淨買(張)": round(foreign_net, 0),
        "投信淨買(張)": round(trust_net, 0),
        "自營淨買(張)": round(dealer_net, 0),
        "三大合計(張)": round(combined_net, 0),
        "連續買超天":  consec,
        "買超天數":    buy_days,
        "觀察天數":    total,
        "買超比例":    round(buy_days / total * 100, 1),
    }


def batch_institutional_scan(stock_list, start_date, token, min_consec, min_buy_ratio):
    """
    批次掃描三大法人，篩選符合條件的股票
    條件：連續買超天數 >= min_consec 或 買超比例 >= min_buy_ratio
    """
    bar     = st.progress(0, text="📊 Module 2：掃描三大法人...")
    total   = len(stock_list)
    results = []

    for i, sid in enumerate(stock_list):
        df = fetch_institutional(sid, start_date, token)
        if not df.empty:
            summary = analyze_institutional(sid, df, days=20)
            if summary:
                passed = (
                    summary["連續買超天"] >= min_consec or
                    summary["買超比例"]   >= min_buy_ratio
                )
                if passed:
                    results.append(summary)
        bar.progress((i+1)/total, text=f"📊 M2 掃描 {i+1}/{total}：{sid}")
        if (i+1) % 10 == 0:
            time.sleep(0.3)

    bar.empty()
    if not results:
        return pd.DataFrame()

    out = pd.DataFrame(results)

    # 補公司名稱
    names = {}
    for sid in out["stock_id"].tolist():
        names[sid] = fetch_stock_name(sid, token)
        time.sleep(0.05)
    out.insert(1, "公司名稱", out["stock_id"].map(names))

    # 信號強度標籤
    def signal_label(row):
        if row["連續買超天"] >= 5:
            return "🔥 強力買超"
        elif row["連續買超天"] >= 3:
            return "✅ 持續買超"
        elif row["買超比例"] >= 70:
            return "✅ 高頻買超"
        else:
            return "👀 值得觀察"

    out["信號強度"] = out.apply(signal_label, axis=1)
    return out.sort_values("連續買超天", ascending=False).reset_index(drop=True)


# ════════════════════════════════════════════════════════════
#  交叉比對：M1 × M2
# ════════════════════════════════════════════════════════════

def cross_compare(m1_df: pd.DataFrame, m2_df: pd.DataFrame) -> pd.DataFrame:
    """
    找出同時通過 M1（業績加速）和 M2（法人買超）的股票
    """
    if m1_df.empty or m2_df.empty:
        return pd.DataFrame()

    m1_ids = set(m1_df["股票代號"].tolist())
    m2_ids = set(m2_df["stock_id"].tolist())
    common = m1_ids & m2_ids

    if not common:
        return pd.DataFrame()

    m1_sub = m1_df[m1_df["股票代號"].isin(common)].copy()
    m2_sub = m2_df[m2_df["stock_id"].isin(common)][
        ["stock_id","三大合計(張)","連續買超天","買超比例","信號強度"]
    ].copy()
    m2_sub = m2_sub.rename(columns={"stock_id": "股票代號"})

    merged = m1_sub.merge(m2_sub, on="股票代號", how="inner")

    # 綜合評分（加速斜率 × 連續買超天）
    merged["綜合評分"] = (
        merged["加速斜率"] * 0.5 +
        merged["連續買超天"] * 0.5
    ).round(2)

    return merged.sort_values("綜合評分", ascending=False).reset_index(drop=True)


# ════════════════════════════════════════════════════════════
#  Sidebar
# ════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🐋 大戶思維\n#### 投資導航系統 v2.0")
    st.divider()

    cloud_token = get_token()
    if cloud_token:
        st.success("✅ FinMind Token 已載入")
        token_to_use = cloud_token
    else:
        st.markdown("#### 🔑 FinMind Token（必填）")
        token_to_use = st.text_input(
            "貼上你的 Token",
            type="password",
            placeholder="finmindtrade.com 免費申請",
        )

    st.divider()
    st.markdown("#### 📅 Module 1 設定")
    months_back      = st.slider("回溯月數", 3, 6, 5)
    min_yoy          = st.number_input("最低 YoY 成長率 (%)", value=10.0, step=5.0)
    min_slope        = st.number_input("最低加速斜率", value=0.0, step=0.5)
    margin_threshold = st.slider("毛利率警戒線 (%)", 1, 30, 10)

    st.divider()
    st.markdown("#### 📊 Module 2 設定")
    m2_days      = st.slider("法人觀察天數", 5, 30, 20,
                              help="分析最近幾個交易日的法人動向")
    min_consec   = st.slider("最低連續買超天數", 1, 10, 3,
                              help="連續幾天三大法人合計買超")
    min_buy_ratio= st.slider("最低買超比例 (%)", 30, 90, 60,
                              help="觀察期間買超天數佔比")

    st.divider()
    st.markdown("#### 📋 自訂股票（選填）")
    custom_input = st.text_input(
        "額外加入股票代號",
        placeholder="例：2330,6415",
        help="逗號分隔，加入預設清單",
    )

    st.divider()
    st.caption(f"預設掃描 {len(WATCHLIST)} 支熱門股")
    st.caption("資料來源：FinMind Open API")
    st.caption("本系統僅供研究參考，不構成投資建議")

    run_btn = st.button(
        "🚀 開始分析",
        use_container_width=True,
        type="primary",
        disabled=not token_to_use,
    )


# ════════════════════════════════════════════════════════════
#  主畫面
# ════════════════════════════════════════════════════════════

st.title("🐋 大戶思維投資導航系統")
st.caption("Module 1 成長動能  ×  Module 2-1 三大法人  ｜  v2.0")

tab_cross, tab_m1, tab_m2, tab_guide, tab_road = st.tabs([
    "🎯 交叉比對（最強訊號）",
    "📈 Module 1 成長篩選",
    "📊 Module 2 法人追蹤",
    "📖 使用說明",
    "🗺 開發路線圖",
])

# ── 使用說明 ──────────────────────────────────────────────────
with tab_guide:
    st.markdown("""
    ### 📱 操作方式
    1. 左側輸入 **FinMind Token**（必填）
    2. 調整 M1、M2 參數
    3. 按「🚀 開始分析」（約 4～6 分鐘）
    4. 優先看「🎯 交叉比對」Tab

    ### 🎯 三個 Tab 的意義
    | Tab | 內容 | 優先度 |
    |-----|------|--------|
    | **🎯 交叉比對** | M1+M2 都通過，最強訊號 | ⭐⭐⭐⭐⭐ |
    | **📈 Module 1** | 業績加速成長名單 | ⭐⭐⭐ |
    | **📊 Module 2** | 法人持續買超名單 | ⭐⭐⭐ |

    ### 📊 Module 2 欄位說明
    | 欄位 | 說明 |
    |------|------|
    | **三大合計(張)** | 近期外資+投信+自營淨買張數，正值=買超 |
    | **連續買超天** | 連續幾個交易日三大合計為正 |
    | **買超比例(%)** | 觀察期間買超天數佔比 |
    | **信號強度** | 🔥強力 / ✅持續 / 👀觀察 |

    ### ⚠️ 重要提醒
    通過篩選不代表立即買進！仍需：
    - 確認技術面是否突破
    - 確認是否為「第一根」而非追高
    - 設定停損，確認賺賠比達 1:3
    """)

# ── 開發路線圖 ────────────────────────────────────────────────
with tab_road:
    st.markdown("""
    ### ✅ 已完成
    - Module 1：成長動能篩選器
    - Module 1：做帳偵測（毛利率）
    - Module 2-1：三大法人買賣超追蹤
    - M1 × M2 交叉比對

    ### 🔄 Module 2 規劃中
    - Module 2-2：抗跌強勢偵測（大盤跌時誰最抗跌）
    - Module 2-3：發動點偵測（突破長期盤整的第一根紅棒）

    ### 📅 後續模組
    - Module 3：政策新聞 NLP 分析
    - Module 4：停損紀律控制台
    """)

# ── 主分析邏輯 ────────────────────────────────────────────────
if not token_to_use:
    with tab_cross:
        st.markdown("""
        <div class="alert-blue">
            <strong>🔑 請先在左側輸入 FinMind Token</strong><br>
            前往 <a href="https://finmindtrade.com" target="_blank">finmindtrade.com</a>
            免費註冊，每日 500 次免費額度。
        </div>
        """, unsafe_allow_html=True)

elif not run_btn:
    with tab_cross:
        st.markdown("""
        <div style="text-align:center;padding:60px 0;color:#506880;">
            <div style="font-size:56px">🐋</div>
            <p style="font-size:18px;margin-top:16px;">Token 已就緒，按左側「開始分析」</p>
            <p style="font-size:12px;">M1 + M2 完整掃描約 4～6 分鐘</p>
        </div>
        """, unsafe_allow_html=True)

else:
    # ── 建立掃描清單 ──
    scan_list = WATCHLIST.copy()
    if custom_input.strip():
        extras = [s.strip() for s in custom_input.split(",")
                  if s.strip().isdigit() and 4 <= len(s.strip()) <= 6]
        scan_list = list(dict.fromkeys(scan_list + extras))

    # ── 計算日期範圍 ──
    m1_start = (datetime.today() - timedelta(days=30*(months_back+13))).strftime("%Y-%m-%d")
    m2_start = (datetime.today() - timedelta(days=m2_days + 10)).strftime("%Y-%m-%d")

    # ════ MODULE 1 ════
    with tab_m1:
        st.subheader("📈 Module 1 — 成長動能篩選")
        st.info(f"掃描 {len(scan_list)} 支股票的月營收資料...")

        raw_df = batch_revenue_scan(scan_list, m1_start, token_to_use)

        if raw_df.empty:
            st.error("❌ 月營收資料抓取失敗，請確認 Token。")
            st.stop()

        yoy_df  = calc_yoy(raw_df)
        m1_scanned = yoy_df["stock_id"].nunique()
        st.success(f"✅ 成功取得 {m1_scanned} 支股票營收資料")

        with st.spinner("⚙️ 執行成長動能篩選..."):
            m1_result = run_growth_scanner(yoy_df, min_yoy, min_slope, months_back, token_to_use)

        if not m1_result.empty:
            m1_result = run_fake_detector(m1_result, token_to_use, margin_threshold)

        # 統計
        c1, c2, c3, c4 = st.columns(4)
        m1_passed  = len(m1_result)
        m1_flagged = (
            len(m1_result[m1_result["毛利率狀態"].str.contains("⚠️", na=False)])
            if "毛利率狀態" in m1_result.columns else 0
        )
        c1.metric("掃描股票數",   f"{m1_scanned}")
        c2.metric("通過成長篩選", f"{m1_passed}")
        c3.metric("⚠️ 毛利率異常", f"{m1_flagged}")
        c4.metric("✅ M1 最終候選", f"{m1_passed - m1_flagged}")

        if m1_result.empty:
            st.markdown('<div class="alert-yellow">無股票通過 M1 條件，請調低 YoY 門檻。</div>',
                        unsafe_allow_html=True)
        else:
            d_cols = ["股票代號","公司名稱","最新YoY(%)","加速斜率","連3月正成長","成長加速中"]
            if "毛利率狀態" in m1_result.columns:
                d_cols.append("毛利率狀態")

            def hl(val):
                if "⚠️" in str(val): return "background:#3a1010;color:#ff6b6b"
                if "✅" in str(val):  return "background:#0d2015;color:#56d364"
                return ""

            styled = (
                m1_result[d_cols].style
                .map(hl, subset=["毛利率狀態"] if "毛利率狀態" in d_cols else [])
                .format({"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}"})
                .background_gradient(subset=["加速斜率"], cmap="YlGn")
            )
            st.dataframe(styled, use_container_width=True, height=400)
            csv = m1_result[d_cols].to_csv(index=False, encoding="utf-8-sig")
            st.download_button("📥 下載 M1 CSV", data=csv,
                               file_name=f"m1_{datetime.today().strftime('%Y%m%d')}.csv",
                               mime="text/csv")

    # ════ MODULE 2 ════
    with tab_m2:
        st.subheader("📊 Module 2-1 — 三大法人買賣超")
        st.info(f"掃描 {len(scan_list)} 支股票，觀察最近 {m2_days} 個交易日...")
        st.markdown(f"""
        <div class="alert-blue">
            篩選條件：<strong>連續買超 ≥ {min_consec} 天</strong>
            或 <strong>買超比例 ≥ {min_buy_ratio}%</strong>
        </div>
        """, unsafe_allow_html=True)

        m2_result = batch_institutional_scan(
            scan_list, m2_start, token_to_use, min_consec, min_buy_ratio
        )

        if m2_result.empty:
            st.markdown('<div class="alert-yellow">無股票通過 M2 條件，可試著降低門檻。</div>',
                        unsafe_allow_html=True)
        else:
            c1, c2, c3 = st.columns(3)
            strong = len(m2_result[m2_result["信號強度"].str.contains("🔥")])
            steady = len(m2_result[m2_result["信號強度"].str.contains("✅")])
            c1.metric("通過 M2 篩選", f"{len(m2_result)}")
            c2.metric("🔥 強力買超",  f"{strong}")
            c3.metric("✅ 持續買超",  f"{steady}")

            m2_cols = ["stock_id","公司名稱","三大合計(張)","外資淨買(張)",
                       "投信淨買(張)","連續買超天","買超比例","信號強度"]
            m2_cols = [c for c in m2_cols if c in m2_result.columns]

            def hl2(val):
                if "🔥" in str(val): return "background:#1a0d00;color:#f0a500"
                if "✅" in str(val):  return "background:#0d2015;color:#56d364"
                if "👀" in str(val):  return "background:#0a1e30;color:#4a9eff"
                return ""

            styled2 = (
                m2_result[m2_cols].style
                .map(hl2, subset=["信號強度"])
                .format({"買超比例":"{:.1f}%",
                         "三大合計(張)":"{:.0f}",
                         "外資淨買(張)":"{:.0f}",
                         "投信淨買(張)":"{:.0f}"})
                .background_gradient(subset=["連續買超天"], cmap="YlGn")
            )
            st.dataframe(styled2, use_container_width=True, height=400)

            csv2 = m2_result[m2_cols].to_csv(index=False, encoding="utf-8-sig")
            st.download_button("📥 下載 M2 CSV", data=csv2,
                               file_name=f"m2_{datetime.today().strftime('%Y%m%d')}.csv",
                               mime="text/csv")

    # ════ 交叉比對 ════
    with tab_cross:
        st.subheader("🎯 交叉比對 — M1 × M2 最強訊號")
        st.markdown("""
        <div class="alert-gold">
            <strong>同時滿足：業績加速成長（M1）＋ 三大法人持續買超（M2）</strong><br>
            這代表基本面與籌碼面雙重確認，是最值得深入研究的標的。
        </div>
        """, unsafe_allow_html=True)

        # 執行比對
        cross_result = pd.DataFrame()
        if 'm1_result' in dir() and 'm2_result' in dir():
            if not m1_result.empty and not m2_result.empty:
                cross_result = cross_compare(m1_result, m2_result)

        if cross_result.empty:
            st.markdown("""
            <div class="alert-yellow">
                目前無股票同時通過 M1 和 M2 篩選。<br>
                建議：降低其中一個模組的門檻，或等下次月營收公布後再掃描。
            </div>
            """, unsafe_allow_html=True)

            # 仍顯示 M1、M2 各自的候選數
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📈 M1 候選（業績加速）**")
                if 'm1_result' in dir() and not m1_result.empty:
                    for _, r in m1_result.head(5).iterrows():
                        st.markdown(f"· {r['股票代號']} {r['公司名稱']}  YoY {r['最新YoY(%)']:.1f}%")
            with col2:
                st.markdown("**📊 M2 候選（法人買超）**")
                if 'm2_result' in dir() and not m2_result.empty:
                    for _, r in m2_result.head(5).iterrows():
                        st.markdown(f"· {r['stock_id']} {r['公司名稱']}  連買 {r['連續買超天']} 天")
        else:
            st.markdown(f"""
            <div class="alert-green">
                🎯 找到 <strong>{len(cross_result)}</strong> 支同時通過 M1 + M2 的標的！
            </div>
            """, unsafe_allow_html=True)

            # 統計
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("M1 候選數",  f"{len(m1_result)}")
            c2.metric("M2 候選數",  f"{len(m2_result)}")
            c3.metric("🎯 交叉命中", f"{len(cross_result)}")
            c4.metric("最高綜合評分", f"{cross_result['綜合評分'].max():.2f}")

            st.divider()

            cross_cols = ["股票代號","公司名稱","最新YoY(%)","加速斜率",
                          "三大合計(張)","連續買超天","買超比例","信號強度","綜合評分"]
            if "毛利率狀態" in cross_result.columns:
                cross_cols.insert(4, "毛利率狀態")
            cross_cols = [c for c in cross_cols if c in cross_result.columns]

            def hl3(val):
                if "🔥" in str(val): return "background:#1a0d00;color:#f0a500"
                if "⚠️" in str(val): return "background:#3a1010;color:#ff6b6b"
                if "✅" in str(val):  return "background:#0d2015;color:#56d364"
                if "👀" in str(val):  return "background:#0a1e30;color:#4a9eff"
                return ""

            fmt = {"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}",
                   "三大合計(張)":"{:.0f}","買超比例":"{:.1f}%","綜合評分":"{:.2f}"}

            styled3 = (
                cross_result[cross_cols].style
                .map(hl3, subset=[c for c in ["信號強度","毛利率狀態"] if c in cross_cols])
                .format({k:v for k,v in fmt.items() if k in cross_cols})
                .background_gradient(subset=["綜合評分"], cmap="YlOrRd")
            )
            st.dataframe(styled3, use_container_width=True, height=420)

            csv3 = cross_result[cross_cols].to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 下載交叉比對 CSV",
                data=csv3,
                file_name=f"whale_cross_{datetime.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

            # 個股詳細提示
            st.divider()
            st.markdown("#### 📋 各標的重點提示")
            for _, row in cross_result.iterrows():
                signal = row.get("信號強度","")
                margin = row.get("毛利率狀態","")
                warn   = "⚠️" in str(margin)

                box_class = "alert-red" if warn else "alert-green"
                st.markdown(f"""
                <div class="{box_class}">
                    <strong>{row['股票代號']} {row['公司名稱']}</strong>
                    &nbsp;｜&nbsp; YoY <strong>{row['最新YoY(%)']:.1f}%</strong>
                    &nbsp;｜&nbsp; 連買 <strong>{int(row['連續買超天'])}</strong> 天
                    &nbsp;｜&nbsp; {signal}
                    {"&nbsp;｜&nbsp; ⚠️ 毛利率需注意" if warn else ""}
                </div>
                """, unsafe_allow_html=True)
