# ════════════════════════════════════════════════════════════
#  大戶思維投資導航系統 — Streamlit Cloud 版
# ════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import time

# ── 頁面設定 ─────────────────────────────────────────────────
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
    .alert-green {
        background: #0d2015; border-left: 4px solid #56d364;
        padding: 10px 14px; border-radius: 4px; margin: 6px 0;
    }
    .alert-yellow {
        background: #2a1f00; border-left: 4px solid #f0a500;
        padding: 10px 14px; border-radius: 4px; margin: 6px 0;
    }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  雲端版：Token 從 Streamlit Secrets 讀取
#  （本機測試時從 .streamlit/secrets.toml 讀取）
# ════════════════════════════════════════════════════════════

def get_finmind_token() -> str:
    """
    優先順序：
    1. Streamlit Cloud Secrets（部署後自動使用）
    2. 使用者在側邊欄手動輸入（本機或備用）
    """
    try:
        return st.secrets["FINMIND_TOKEN"]
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════
#  資料抓取
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def fetch_revenue_mops(year: int, month: int) -> pd.DataFrame:
    roc_year = year - 1911
    url = (
        f"https://mops.twse.com.tw/nas/t21/sii/"
        f"t21sc03_{roc_year}_{month}_0.html"
    )
    try:
        tables = pd.read_html(url, encoding="big5", header=[0, 1])
        for t in tables:
            t.columns = [
                "_".join(str(c) for c in col).strip() for col in t.columns
            ]
            col_map = {}
            for c in t.columns:
                if "代號" in c or "代碼" in c:
                    col_map[c] = "stock_id"
                elif "名稱" in c:
                    col_map[c] = "name"
                elif "當月營收" in c:
                    col_map[c] = "revenue"
                elif "去年同月" in c and "增減" in c:
                    col_map[c] = "yoy_pct"
            if "stock_id" in col_map.values() and "revenue" in col_map.values():
                t = t.rename(columns=col_map)
                t = t[list(col_map.values())].copy()
                t["year_month"] = f"{year}-{month:02d}"
                t["revenue"]    = pd.to_numeric(t["revenue"], errors="coerce")
                t["yoy_pct"]    = pd.to_numeric(
                    t.get("yoy_pct", pd.Series(dtype=float)), errors="coerce"
                )
                t["stock_id"]   = t["stock_id"].astype(str).str.strip()
                return t.dropna(subset=["stock_id", "revenue"])
    except Exception as e:
        st.warning(f"⚠️ {year}-{month:02d} 抓取失敗：{e}")
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def build_history(months: int = 6) -> pd.DataFrame:
    frames = []
    today  = datetime.today()
    bar    = st.progress(0, text="正在從 MOPS 抓取月營收...")
    for i in range(months):
        dt = today - timedelta(days=30 * (i + 1))
        df = fetch_revenue_mops(dt.year, dt.month)
        if not df.empty:
            frames.append(df)
        bar.progress((i + 1) / months, text=f"已載入 {dt.year}-{dt.month:02d}")
        time.sleep(0.5)   # 雲端版稍微放慢，對 MOPS 友善
    bar.empty()
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_gross_margin(stock_id: str, token: str) -> float | None:
    if not token:
        return None
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset":    "TaiwanStockFinancialStatements",
        "data_id":    stock_id,
        "start_date": "2023-01-01",
        "token":      token,
    }
    try:
        r   = requests.get(url, params=params, timeout=10)
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

def run_growth_scanner(df: pd.DataFrame) -> pd.DataFrame:
    df      = df.sort_values(["stock_id", "year_month"])
    results = []
    for sid, grp in df.groupby("stock_id"):
        grp = grp.tail(6).reset_index(drop=True)
        if len(grp) < 3 or grp["yoy_pct"].isna().sum() > 2:
            continue
        yoy   = grp["yoy_pct"].fillna(0).values
        slope = float(np.polyfit(range(len(yoy)), yoy, 1)[0])
        l3ok  = bool(all(v > 0 for v in yoy[-3:]))
        accel = slope > 0
        results.append({
            "股票代號":    sid,
            "公司名稱":    grp["name"].iloc[-1] if "name" in grp.columns else "—",
            "最新YoY(%)":  round(float(yoy[-1]), 1),
            "加速斜率":    round(slope, 2),
            "連3月正成長": "✅" if l3ok  else "❌",
            "成長加速中":  "✅" if accel else "❌",
            "_pass":       l3ok and accel,
        })
    out = pd.DataFrame(results)
    if out.empty:
        return out
    return (
        out[out["_pass"]]
        .drop(columns=["_pass"])
        .sort_values("加速斜率", ascending=False)
        .reset_index(drop=True)
    )


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
        time.sleep(0.15)
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

    st.markdown("#### 📅 資料設定")
    months_back = st.slider("回溯月數", 3, 6, 5)

    st.markdown("#### 📈 成長門檻")
    min_yoy   = st.number_input("最低 YoY 成長率 (%)", value=10.0, step=5.0)
    min_slope = st.number_input("最低加速斜率", value=0.0, step=0.5)

    st.markdown("#### 🔍 做帳偵測")

    # 嘗試從 Secrets 讀取 token
    cloud_token = get_finmind_token()
    if cloud_token:
        st.success("✅ FinMind Token 已從雲端設定載入")
        token_to_use = cloud_token
    else:
        # 沒有 Secrets 時，讓使用者手動輸入
        manual_token = st.text_input(
            "FinMind Token（選填）",
            type="password",
            placeholder="貼上你的 token，或留空跳過",
        )
        token_to_use = manual_token

    margin_threshold = st.slider("毛利率警戒線 (%)", 1, 30, 10)

    st.divider()
    st.caption("資料來源：MOPS / FinMind Open API")
    st.caption("本系統僅供研究參考，不構成投資建議")

    run_btn = st.button("🚀 開始分析", use_container_width=True, type="primary")


# ════════════════════════════════════════════════════════════
#  主畫面
# ════════════════════════════════════════════════════════════

st.title("🐋 大戶思維投資導航系統")
st.caption("Module 1 — 成長動能篩選器 ｜ Streamlit Cloud 版")

tab_result, tab_guide, tab_roadmap = st.tabs(
    ["📊 篩選結果", "📖 使用說明", "🗺 開發路線圖"]
)

# ── 使用說明 ──────────────────────────────────────────────────
with tab_guide:
    st.markdown("""
    ### 三大篩選邏輯

    | 條件 | 意義 |
    |------|------|
    | **連 3 月 YoY > 0** | 持續正成長，供不應求訊號 |
    | **斜率 > 0** | 成長在加速，不是趨緩 |
    | **毛利率正常** | 排除過水單 / 假業績 |

    ### FinMind Token 申請（免費）
    1. 前往 [finmindtrade.com](https://finmindtrade.com) 註冊
    2. 登入 → 個人資料 → 複製 API Token
    3. 貼到左側欄位，或請管理員設定到 Streamlit Secrets

    ### 操作流程
    1. 左側設定參數
    2. 按「開始分析」
    3. 等待約 1～2 分鐘（雲端抓資料）
    4. 查看結果，可下載 CSV
    """)

# ── 開發路線圖 ────────────────────────────────────────────────
with tab_roadmap:
    st.markdown("""
    ### 已完成
    - ✅ Module 1：成長動能篩選器（YoY 斜率加速）
    - ✅ Module 1：做帳偵測（毛利率異常警示）
    - ✅ Streamlit Cloud 雲端部署

    ### 開發中
    - 🔄 Module 1：P&Q 產業訊號（TrendForce RSS）
    - 🔄 Module 2：大戶籌碼追蹤引擎
    - 🔄 Module 3：政策新聞 NLP 分析
    - 🔄 Module 4：停損紀律控制台
    """)

# ── 篩選結果 ──────────────────────────────────────────────────
with tab_result:
    if not run_btn:
        st.markdown("""
        <div style="text-align:center;padding:70px 0;color:#506880;">
            <div style="font-size:56px">🐋</div>
            <p style="font-size:18px;margin-top:16px;">設定左側參數後，按「開始分析」</p>
            <p style="font-size:12px;">首次執行約 1～2 分鐘</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Step 1：抓資料
        history = build_history(months=months_back)
        if history.empty:
            st.error("❌ 資料抓取失敗，請稍後再試。")
            st.stop()

        total_stocks = history["stock_id"].nunique()
        st.success(f"✅ 載入 {len(history):,} 筆記錄，共 {total_stocks:,} 支股票")

        # Step 2：成長篩選
        with st.spinner("⚙️ 執行成長動能篩選..."):
            candidates = run_growth_scanner(history)

        if not candidates.empty:
            candidates = candidates[
                (candidates["最新YoY(%)"] >= min_yoy) &
                (candidates["加速斜率"]   >= min_slope)
            ]

        # Step 3：做帳偵測
        if token_to_use and not candidates.empty:
            candidates = run_fake_detector(candidates, token_to_use, margin_threshold)

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
        c1.metric("掃描股票數",   f"{total_stocks:,}")
        c2.metric("通過成長篩選", f"{passed}")
        c3.metric("⚠️ 毛利率異常", f"{flagged}" if token_to_use else "未偵測")
        c4.metric("✅ 最終候選",   f"{passed - flagged}")
        st.divider()

        # 結果表格
        if candidates.empty:
            st.markdown("""
            <div class="alert-yellow">
                目前無股票通過所有條件，可試著調低 YoY 門檻或縮短回溯月數。
            </div>
            """, unsafe_allow_html=True)
        else:
            st.subheader(f"📋 候選名單（{len(candidates)} 支）")

            display_cols = [
                "股票代號", "公司名稱", "最新YoY(%)", "加速斜率",
                "連3月正成長", "成長加速中",
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
                    subset=["毛利率狀態"] if "毛利率狀態" in display_cols else [],
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

            # 做帳警示清單
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
