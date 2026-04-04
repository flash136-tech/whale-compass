# ════════════════════════════════════════════════════════════
#  大戶思維投資導航系統 — Streamlit Cloud 版 v1.3
#  資料來源改為 FinMind API（穩定，免費版可用）
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
    .alert-blue {
        background: #0a1e30; border-left: 4px solid #4a9eff;
        padding: 10px 14px; border-radius: 4px; margin: 6px 0;
    }
</style>
""", unsafe_allow_html=True)

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


# ════════════════════════════════════════════════════════════
#  Token 讀取
# ════════════════════════════════════════════════════════════

def get_token() -> str:
    try:
        return st.secrets["FINMIND_TOKEN"]
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════
#  月營收資料（FinMind API）
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def fetch_all_revenue(start_date: str, token: str) -> pd.DataFrame:
    """
    從 FinMind 抓取全市場月營收資料
    dataset: TaiwanStockMonthRevenue
    免費版限制：不帶 token 仍可抓，但有每日次數限制
    """
    params = {
        "dataset":    "TaiwanStockMonthRevenue",
        "start_date": start_date,
    }
    if token:
        params["token"] = token

    try:
        r    = requests.get(FINMIND_URL, params=params, timeout=30)
        data = r.json()

        if data.get("status") != 200:
            st.error(f"❌ FinMind API 錯誤：{data.get('msg', '未知錯誤')}")
            return pd.DataFrame()

        df = pd.DataFrame(data.get("data", []))
        if df.empty:
            return pd.DataFrame()

        # 欄位整理
        df = df.rename(columns={
            "stock_id":      "stock_id",
            "revenue":       "revenue",
            "revenue_month": "month",
            "revenue_year":  "year",
        })
        df["year_month"] = df.apply(
            lambda r: f"{int(r['year'])}-{int(r['month']):02d}", axis=1
        )
        df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
        return df.dropna(subset=["stock_id", "revenue"])

    except Exception as e:
        st.error(f"❌ 資料抓取失敗：{e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_revenue_yoy(start_date: str, token: str) -> pd.DataFrame:
    """
    計算每支股票每個月的 YoY 成長率
    """
    df = fetch_all_revenue(start_date, token)
    if df.empty:
        return df

    df = df.sort_values(["stock_id", "year", "month"])

    # 計算 YoY：與去年同月比較
    df["revenue_last_year"] = df.groupby(
        ["stock_id", "month"]
    )["revenue"].shift(1)

    df["yoy_pct"] = (
        (df["revenue"] - df["revenue_last_year"])
        / df["revenue_last_year"].abs() * 100
    ).round(2)

    return df.dropna(subset=["yoy_pct"])


@st.cache_data(ttl=3600)
def fetch_company_names(token: str) -> dict:
    """抓取股票名稱對照表"""
    params = {"dataset": "TaiwanStockInfo"}
    if token:
        params["token"] = token
    try:
        r    = requests.get(FINMIND_URL, params=params, timeout=15)
        data = r.json().get("data", [])
        df   = pd.DataFrame(data)
        if not df.empty and "stock_id" in df.columns and "stock_name" in df.columns:
            return dict(zip(df["stock_id"], df["stock_name"]))
    except Exception:
        pass
    return {}


@st.cache_data(ttl=3600)
def fetch_gross_margin(stock_id: str, token: str):
    """抓取最新毛利率"""
    if not token:
        return None
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
#  分析核心
# ════════════════════════════════════════════════════════════

def run_growth_scanner(
    df: pd.DataFrame,
    name_map: dict,
    min_yoy: float,
    min_slope: float,
) -> pd.DataFrame:
    """
    篩選條件：
    1. 連續 3 個月 YoY > min_yoy
    2. YoY 斜率 > min_slope（成長在加速）
    """
    df      = df.sort_values(["stock_id", "year", "month"])
    results = []

    for sid, grp in df.groupby("stock_id"):
        grp = grp.tail(6).reset_index(drop=True)
        if len(grp) < 3:
            continue

        yoy = grp["yoy_pct"].fillna(0).values
        if len(yoy) < 3:
            continue

        slope = float(np.polyfit(range(len(yoy)), yoy, 1)[0])
        l3ok  = bool(all(v > min_yoy for v in yoy[-3:]))
        accel = slope > min_slope

        if not (l3ok and accel):
            continue

        results.append({
            "股票代號":    str(sid),
            "公司名稱":    name_map.get(str(sid), "—"),
            "最新YoY(%)":  round(float(yoy[-1]), 1),
            "加速斜率":    round(slope, 2),
            "連3月正成長": "✅",
            "成長加速中":  "✅",
        })

    out = pd.DataFrame(results)
    if out.empty:
        return out
    return out.sort_values("加速斜率", ascending=False).reset_index(drop=True)


def run_fake_detector(
    candidates: pd.DataFrame, token: str, threshold: float
) -> pd.DataFrame:
    if candidates.empty or not token:
        return candidates
    risks = []
    bar   = st.progress(0, text="🔍 毛利率偵測中...")
    total = min(len(candidates), 20)
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

    # Token 設定
    cloud_token = get_token()
    if cloud_token:
        st.success("✅ FinMind Token 已載入")
        token_to_use = cloud_token
    else:
        st.markdown("#### 🔑 FinMind Token")
        st.markdown(
            "<div class='alert-blue' style='font-size:12px'>"
            "免費申請：<a href='https://finmindtrade.com' target='_blank'>"
            "finmindtrade.com</a><br>註冊後貼上 Token 即可使用</div>",
            unsafe_allow_html=True,
        )
        manual_token = st.text_input(
            "貼上你的 Token",
            type="password",
            placeholder="必填，否則無法抓取資料",
        )
        token_to_use = manual_token

    st.divider()
    st.markdown("#### 📅 資料設定")
    months_back = st.slider("回溯月數", 3, 12, 6)

    st.markdown("#### 📈 成長門檻")
    min_yoy   = st.number_input("最低 YoY 成長率 (%)", value=10.0, step=5.0)
    min_slope = st.number_input("最低加速斜率", value=0.0, step=0.5)

    st.markdown("#### 🔍 做帳偵測")
    margin_threshold = st.slider("毛利率警戒線 (%)", 1, 30, 10)

    st.divider()
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
st.caption("Module 1 — 成長動能篩選器 ｜ v1.3")

tab_result, tab_guide, tab_roadmap = st.tabs(
    ["📊 篩選結果", "📖 使用說明", "🗺 開發路線圖"]
)

with tab_guide:
    st.markdown("""
    ### 📱 操作方式
    1. 點左上角「**>**」展開側邊欄
    2. 輸入 **FinMind Token**（必填）
    3. 調整篩選參數
    4. 按「🚀 開始分析」
    5. 等待約 **30～60 秒**
    6. 查看結果，可下載 CSV

    ### 🔑 FinMind Token 免費申請
    1. 前往 [finmindtrade.com](https://finmindtrade.com)
    2. 點右上角「註冊」
    3. Email 驗證後登入
    4. 點「個人資料」→ 複製 Token
    5. 貼到左側欄位

    **免費額度：每日 500 次，個人使用完全足夠**

    ### 🎯 可以獲得哪些關鍵資訊？
    | 資訊 | 說明 |
    |------|------|
    | **股票代號／名稱** | 通過篩選的標的 |
    | **最新 YoY (%)** | 本月 vs 去年同月營收成長率 |
    | **加速斜率** | 數字越大，成長加速越明顯 |
    | **連3月正成長** | 確認成長持續性 |
    | **成長加速中** | 確認趨勢走強 |
    | **毛利率狀態** | 偵測過水單 / 做帳風險 |

    ### ⚙️ 參數建議值
    | 參數 | 建議值 | 說明 |
    |------|--------|------|
    | 回溯月數 | 6～12 | 越多越準 |
    | 最低 YoY | 10～20% | 越高候選越精 |
    | 最低加速斜率 | 0～2 | 0 = 只要有加速 |
    | 毛利率警戒線 | 10% | 低於此值標記⚠️ |
    """)

with tab_roadmap:
    st.markdown("""
    ### ✅ 已完成
    - Module 1：成長動能篩選器（YoY 斜率加速）
    - Module 1：做帳偵測（毛利率異常警示）
    - Streamlit Cloud 雲端部署
    - 資料來源升級（FinMind API，穩定可靠）

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
            免費註冊取得，每日 500 次免費額度。
        </div>
        """, unsafe_allow_html=True)
    elif not run_btn:
        st.markdown("""
        <div style="text-align:center;padding:70px 0;color:#506880;">
            <div style="font-size:56px">🐋</div>
            <p style="font-size:18px;margin-top:16px;">Token 已輸入，按左側「開始分析」</p>
            <p style="font-size:12px;">約 30～60 秒出結果</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # 計算起始日期
        start_date = (
            datetime.today() - timedelta(days=30 * (months_back + 13))
        ).strftime("%Y-%m-%d")

        # Step 1：抓月營收
        with st.spinner("📡 從 FinMind 抓取月營收資料..."):
            rev_df = fetch_revenue_yoy(start_date, token_to_use)

        if rev_df.empty:
            st.error("❌ 資料抓取失敗，請確認 Token 是否正確。")
            st.stop()

        # 只保留近 months_back 個月
        cutoff = (
            datetime.today() - timedelta(days=30 * months_back)
        ).strftime("%Y-%m")
        rev_df = rev_df[rev_df["year_month"] >= cutoff]

        total_stocks = rev_df["stock_id"].nunique()
        st.success(f"✅ 載入 {len(rev_df):,} 筆記錄，共 {total_stocks:,} 支股票")

        # Step 2：抓公司名稱
        with st.spinner("📋 載入公司名稱..."):
            name_map = fetch_company_names(token_to_use)

        # Step 3：成長篩選
        with st.spinner("⚙️ 執行成長動能篩選..."):
            candidates = run_growth_scanner(
                rev_df, name_map, min_yoy, min_slope
            )

        # Step 4：做帳偵測
        if token_to_use and not candidates.empty:
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
        c1.metric("掃描股票數",    f"{total_stocks:,}")
        c2.metric("通過成長篩選",  f"{passed}")
        c3.metric("⚠️ 毛利率異常", f"{flagged}")
        c4.metric("✅ 最終候選",    f"{passed - flagged}")
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
                .applymap(
                    highlight,
                    subset=(
                        ["毛利率狀態"]
                        if "毛利率狀態" in display_cols else []
                    ),
                )
                .format({"最新YoY(%)": "{:.1f}%", "加速斜率": "{:.2f}"})
                .background_gradient(subset=["加速斜率"], cmap="YlGn")
            )
            st.dataframe(styled, use_container_width=True, height=440)

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
