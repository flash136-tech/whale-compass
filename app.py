# ════════════════════════════════════════════════════════════
#  大戶思維投資導航系統 — Streamlit Cloud 版 v1.5
#  資料來源：FinMind API（個股查詢，免費 Token 可用）
#  掃描範圍：台灣前 100 大熱門股（台灣 50 + 中型 100 精選）
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
</style>
""", unsafe_allow_html=True)

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

# ════════════════════════════════════════════════════════════
#  台灣熱門股清單（台灣 50 + 中型 100 精選，共 100 支）
# ════════════════════════════════════════════════════════════

WATCHLIST = [
    # 台灣 50 核心
    "2330","2317","2454","2382","2308","2303","2881","2882","2891",
    "2886","2884","2885","2892","2883","2887","1301","1303","1326",
    "2002","2105","2207","2357","2379","2395","2408","2412","2474",
    "2603","2609","2615","2801","3008","3045","3711","4904","4938",
    "5871","5876","5880","6505","6669","8046","9910","2823","2880",
    # 半導體 / AI 供應鏈
    "2337","2344","2345","2376","2388","2449","2451","3034","3037",
    "3081","3293","3443","3673","3680","3706","4961","4966","6415",
    "6446","6464","6533","6550","6770","8069","8詣","2367","2385",
    # 電子 / 伺服器
    "2356","2360","2362","2377","2387","2392","2393","2397","2399",
    "3017","3019","3105","3231","3532","4977","5269","6214","6239",
    "6269","6278","6285","6289","6443","6449","6510","6531","6547",
    # 傳產 / 金融
    "1101","1102","1216","1402","1605","2027","2049","2059","2201",
    "2204","2352","2371","2404","2609","2849","3702","4912","5009",
    "5274","6116","6176","9941","9945","2059","1590","2610","2618",
]

# 移除重複並過濾純數字 4～6 碼
WATCHLIST = list(dict.fromkeys(
    s for s in WATCHLIST if s.isdigit() and 4 <= len(s) <= 6
))


# ════════════════════════════════════════════════════════════
#  Token 讀取
# ════════════════════════════════════════════════════════════

def get_token() -> str:
    try:
        return st.secrets["FINMIND_TOKEN"]
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════
#  FinMind 月營收查詢（單一股票）
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
            lambda r: f"{int(r['revenue_year'])}-{int(r['revenue_month']):02d}",
            axis=1,
        )
        return df[["stock_id", "revenue", "revenue_year",
                   "revenue_month", "year_month"]]
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_stock_name(stock_id: str, token: str) -> str:
    params = {
        "dataset": "TaiwanStockInfo",
        "data_id": stock_id,
        "token":   token,
    }
    try:
        r    = requests.get(FINMIND_URL, params=params, timeout=8)
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
        r   = requests.get(FINMIND_URL, params=params, timeout=10)
        df  = pd.DataFrame(r.json().get("data", []))
        if df.empty:
            return None
        gp  = df[df["type"] == "GrossProfit"]["value"].values
        rev = df[df["type"] == "Revenue"]["value"].values
        if len(gp) > 0 and len(rev) > 0 and float(rev[-1]) != 0:
            return round(float(gp[-1]) / float(rev[-1]) * 100, 2)
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════════
#  批次掃描：逐支股票查詢
# ════════════════════════════════════════════════════════════

def batch_scan(stock_list: list, start_date: str, token: str) -> pd.DataFrame:
    """
    逐一查詢每支股票的月營收，計算 YoY 並整合。
    每查完 10 支暫停 0.5 秒，避免觸發 API 限流。
    """
    bar    = st.progress(0, text="📡 開始掃描...")
    total  = len(stock_list)
    frames = []

    for i, sid in enumerate(stock_list):
        df = fetch_stock_revenue(sid, start_date, token)
        if not df.empty:
            frames.append(df)
        bar.progress(
            (i + 1) / total,
            text=f"📡 掃描中 {i+1}/{total}：{sid}"
        )
        if (i + 1) % 10 == 0:
            time.sleep(0.5)

    bar.empty()
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ════════════════════════════════════════════════════════════
#  成長動能分析
# ════════════════════════════════════════════════════════════

def calc_yoy(df: pd.DataFrame) -> pd.DataFrame:
    """計算每支股票的 YoY 成長率"""
    df = df.sort_values(["stock_id", "revenue_year", "revenue_month"])
    df["revenue_last_year"] = df.groupby(
        ["stock_id", "revenue_month"]
    )["revenue"].shift(1)
    df["yoy_pct"] = (
        (df["revenue"] - df["revenue_last_year"])
        / df["revenue_last_year"].abs() * 100
    ).round(2)
    return df.dropna(subset=["yoy_pct"])


def run_growth_scanner(
    df: pd.DataFrame,
    min_yoy: float,
    min_slope: float,
    months_back: int,
    token: str,
) -> pd.DataFrame:
    cutoff = (
        datetime.today() - timedelta(days=30 * months_back)
    ).strftime("%Y-%m")
    df = df[df["year_month"] >= cutoff]
    df = df.sort_values(["stock_id", "year_month"])

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
            "股票代號":    str(sid),
            "公司名稱":    "載入中...",
            "最新YoY(%)":  round(float(yoy[-1]), 1),
            "加速斜率":    round(slope, 2),
            "連3月正成長": "✅",
            "成長加速中":  "✅",
        })

    out = pd.DataFrame(results)
    if out.empty:
        return out

    # 補公司名稱（只補篩選後的少數股票，省 API 次數）
    names = {}
    for sid in out["股票代號"].tolist():
        names[sid] = fetch_stock_name(sid, token)
        time.sleep(0.05)
    out["公司名稱"] = out["股票代號"].map(names)

    return out.sort_values("加速斜率", ascending=False).reset_index(drop=True)


def run_fake_detector(
    candidates: pd.DataFrame, token: str, threshold: float
) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    risks = []
    bar   = st.progress(0, text="🔍 毛利率偵測中...")
    total = min(len(candidates), 15)
    for i, row in candidates.head(total).iterrows():
        m = fetch_gross_margin(str(row["股票代號"]), token)
        if m is None:
            risks.append("—（無資料）")
        elif m < threshold:
            risks.append(f"⚠️ 毛利率僅 {m}%")
        else:
            risks.append(f"✅ {m}%")
        bar.progress((i + 1) / total)
        time.sleep(0.1)
    bar.empty()
    result = candidates.head(total).copy()
    result["毛利率狀態"] = risks
    return result


# ════════════════════════════════════════════════════════════
#  Sidebar
# ════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🐋 大戶思維\n#### 投資導航系統")
    st.divider()

    # Token
    cloud_token = get_token()
    if cloud_token:
        st.success("✅ FinMind Token 已從雲端載入")
        token_to_use = cloud_token
    else:
        st.markdown("#### 🔑 FinMind Token（必填）")
        token_to_use = st.text_input(
            "貼上你的 Token",
            type="password",
            placeholder="finmindtrade.com 免費申請",
        )

    st.divider()
    st.markdown("#### 📅 掃描設定")
    months_back = st.slider("回溯月數", 3, 6, 5)

    st.markdown("#### 📈 成長門檻")
    min_yoy   = st.number_input("最低 YoY 成長率 (%)", value=10.0, step=5.0)
    min_slope = st.number_input("最低加速斜率", value=0.0, step=0.5)

    st.markdown("#### 🔍 做帳偵測")
    margin_threshold = st.slider("毛利率警戒線 (%)", 1, 30, 10)

    st.markdown("#### 📋 自訂股票（選填）")
    custom_input = st.text_input(
        "額外加入的股票代號",
        placeholder="例：2330,6415,3034",
        help="用逗號分隔，會加入預設清單一起掃描",
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
st.caption("Module 1 — 成長動能篩選器 ｜ v1.5")

tab_result, tab_list, tab_guide, tab_roadmap = st.tabs(
    ["📊 篩選結果", "📋 掃描清單", "📖 使用說明", "🗺 開發路線圖"]
)

with tab_list:
    st.markdown(f"### 預設掃描清單（共 {len(WATCHLIST)} 支）")
    st.markdown("""
    涵蓋台灣 50、中型 100 精選、半導體/AI 供應鏈、電子、金融等熱門標的。
    可在左側「自訂股票」欄位額外加入想追蹤的股票代號。
    """)
    cols = st.columns(6)
    for i, sid in enumerate(WATCHLIST):
        cols[i % 6].markdown(f"`{sid}`")

with tab_guide:
    st.markdown("""
    ### 📱 操作方式
    1. 點左上角「**>**」展開側邊欄
    2. 輸入 **FinMind Token**（必填）
    3. 調整參數，可加入自訂股票
    4. 按「🚀 開始分析」
    5. 等待約 **2～3 分鐘**（逐一查詢）
    6. 查看結果，可下載 CSV

    ### 🎯 可以獲得哪些關鍵資訊？
    | 資訊 | 說明 |
    |------|------|
    | **股票代號／名稱** | 通過篩選的標的 |
    | **最新 YoY (%)** | 本月 vs 去年同月營收成長率 |
    | **加速斜率** | 數字越大，成長加速越明顯 |
    | **連3月正成長** | 確認成長持續性 |
    | **成長加速中** | 確認趨勢走強 |
    | **毛利率狀態** | 偵測過水單 / 做帳風險 |

    ### 💡 為什麼需要 Token？
    雲端伺服器的 IP 被 MOPS 封鎖，改用 FinMind API 穩定查詢。
    個股查詢完全在免費額度（每日 500 次）內。
    """)

with tab_roadmap:
    st.markdown("""
    ### ✅ 已完成
    - Module 1：成長動能篩選器
    - Module 1：做帳偵測（毛利率異常）
    - Streamlit Cloud 雲端部署

    ### 🔄 規劃中
    - Module 1：P&Q 產業訊號
    - Module 2：大戶籌碼追蹤
    - Module 3：政策新聞 NLP 分析
    - Module 4：停損紀律控制台
    """)

with tab_result:
    if not token_to_use:
        st.markdown("""
        <div class="alert-blue">
            <strong>🔑 請先在左側輸入 FinMind Token</strong><br>
            前往 <a href="https://finmindtrade.com" target="_blank">finmindtrade.com</a>
            免費註冊，每日 500 次免費額度。
        </div>
        """, unsafe_allow_html=True)
    elif not run_btn:
        st.markdown("""
        <div style="text-align:center;padding:60px 0;color:#506880;">
            <div style="font-size:56px">🐋</div>
            <p style="font-size:18px;margin-top:16px;">Token 已就緒，按左側「開始分析」</p>
            <p style="font-size:12px;">掃描約 100 支股票，需 2～3 分鐘</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # 建立最終股票清單
        scan_list = WATCHLIST.copy()
        if custom_input.strip():
            extras = [
                s.strip() for s in custom_input.split(",")
                if s.strip().isdigit() and 4 <= len(s.strip()) <= 6
            ]
            scan_list = list(dict.fromkeys(scan_list + extras))
            st.info(f"✚ 加入自訂股票：{', '.join(extras)}")

        st.markdown(f"""
        <div class="alert-blue">
            📡 開始掃描 <strong>{len(scan_list)}</strong> 支股票，
            回溯 <strong>{months_back}</strong> 個月資料...
        </div>
        """, unsafe_allow_html=True)

        # 計算起始日期（多抓 13 個月以計算 YoY）
        start_date = (
            datetime.today() - timedelta(days=30 * (months_back + 13))
        ).strftime("%Y-%m-%d")

        # Step 1：批次查詢
        raw_df = batch_scan(scan_list, start_date, token_to_use)

        if raw_df.empty:
            st.error("❌ 查詢失敗，請確認 Token 是否正確，或稍後再試。")
            st.stop()

        # Step 2：計算 YoY
        with st.spinner("⚙️ 計算 YoY 成長率..."):
            yoy_df = calc_yoy(raw_df)

        scanned = yoy_df["stock_id"].nunique()
        st.markdown(f"""
        <div class="alert-green">
            ✅ 成功取得 <strong>{scanned}</strong> 支股票的營收資料
        </div>
        """, unsafe_allow_html=True)

        # Step 3：成長篩選
        with st.spinner("📈 執行成長動能篩選..."):
            candidates = run_growth_scanner(
                yoy_df, min_yoy, min_slope, months_back, token_to_use
            )

        # Step 4：做帳偵測
        if not candidates.empty:
            candidates = run_fake_detector(
                candidates, token_to_use, margin_threshold
            )

        # 統計卡片
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        passed  = len(candidates)
        flagged = (
            len(candidates[
                candidates["毛利率狀態"].str.contains("⚠️", na=False)
            ])
            if "毛利率狀態" in candidates.columns else 0
        )
        c1.metric("掃描股票數",   f"{scanned}")
        c2.metric("通過成長篩選", f"{passed}")
        c3.metric("⚠️ 毛利率異常", f"{flagged}")
        c4.metric("✅ 最終候選",   f"{passed - flagged}")
        st.divider()

        if candidates.empty:
            st.markdown("""
            <div class="alert-yellow">
                目前無股票通過所有條件，可試著調低 YoY 門檻或增加回溯月數。
            </div>
            """, unsafe_allow_html=True)
        else:
            st.subheader(f"📋 候選名單（{len(candidates)} 支）")

            display_cols = [
                "股票代號", "公司名稱", "最新YoY(%)",
                "加速斜率", "連3月正成長", "成長加速中",
            ]
            if "毛利率狀態" in candidates.columns:
                display_cols.append("毛利率狀態")

            def highlight(val):
                if "⚠️" in str(val):
                    return "background:#3a1010;color:#ff6b6b"
                if "✅" in str(val):
                    return "background:#0d2015;color:#56d364"
                return ""

            styled = (
                candidates[display_cols]
                .style
                .map(
                    highlight,
                    subset=(
                        ["毛利率狀態"]
                        if "毛利率狀態" in display_cols else []
                    ),
                )
                .format({"最新YoY(%)": "{:.1f}%", "加速斜率": "{:.2f}"})
                .background_gradient(subset=["加速斜率"], cmap="YlGn")
            )
            st.dataframe(styled, use_container_width=True, height=420)

            csv = candidates[display_cols].to_csv(
                index=False, encoding="utf-8-sig"
            )
            st.download_button(
                "📥 下載 CSV",
                data=csv,
                file_name=f"whale_{datetime.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

            if "毛利率狀態" in candidates.columns:
                risky = candidates[
                    candidates["毛利率狀態"].str.contains("⚠️", na=False)
                ]
                if not risky.empty:
                    st.subheader("🚨 做帳風險警示")
                    for _, row in risky.iterrows():
                        st.markdown(f"""
                        <div class="alert-red">
                            <strong>{row['股票代號']} {row['公司名稱']}</strong>
                            — {row['毛利率狀態']}，營收暴增但獲利品質存疑，建議查核財報。
                        </div>
                        """, unsafe_allow_html=True)
