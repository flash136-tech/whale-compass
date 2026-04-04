# ════════════════════════════════════════════════════════════
#  大戶思維投資導航系統 — Streamlit Cloud 版 v1.2
# ════════════════════════════════════════════════════════════

import ssl
import urllib.request
import io
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
</style>
""", unsafe_allow_html=True)


def get_finmind_token() -> str:
    try:
        return st.secrets["FINMIND_TOKEN"]
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════
#  資料抓取（v1.2 修正：讀進記憶體再用 html5lib 解析）
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def fetch_revenue_mops(year: int, month: int) -> pd.DataFrame:
    roc_year = year - 1911
    url = (
        f"https://mops.twse.com.tw/nas/t21/sii/"
        f"t21sc03_{roc_year}_{month}_0.html"
    )
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(url, context=ctx, timeout=15) as resp:
            raw_bytes = resp.read()

        # 先解碼成字串，再用 StringIO 包裝，徹底解決 non-rewindable 問題
        html_str    = raw_bytes.decode("big5", errors="ignore")
        html_buffer = io.StringIO(html_str)
        tables      = pd.read_html(html_buffer, header=[0, 1], flavor="html5lib")

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
def build_history(months: int = 5) -> pd.DataFrame:
    frames = []
    today  = datetime.today()
    bar    = st.progress(0, text="正在從 MOPS 抓取月營收...")
    for i in range(months):
        dt = today - timedelta(days=30 * (i + 1))
        df = fetch_revenue_mops(dt.year, dt.month)
        if not df.empty:
            frames.append(df)
        bar.progress((i + 1) / months, text=f"已載入 {dt.year}-{dt.month:02d}")
        time.sleep(0.8)
    bar.empty()
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_gross_margin(stock_id: str, token: str):
    if not token:
        return None
    url    = "https://api.finmindtrade.com/api/v4/data"
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
    cloud_token = get_finmind_token()
    if cloud_token:
        st.success("✅ FinMind Token 已載入")
        token_to_use = cloud_token
    else:
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
st.caption("Module 1 — 成長動能篩選器 ｜ v1.2")

tab_result, tab_guide, tab_roadmap = st.tabs(
    ["📊 篩選結果", "📖 使用說明", "🗺 開發路線圖"]
)

with tab_guide:
    st.markdown("""
    ### 📱 操作方式
    1. 點左上角「**>**」展開側邊欄
    2. 調整篩選參數
    3. 按「🚀 開始分析」
    4. 等待約 **1～2 分鐘**
    5. 查看結果，可下載 CSV

    ### 🎯 可以獲得哪些關鍵資訊？
    | 資訊 | 說明 |
    |------|------|
    | **股票代號／名稱** | 通過篩選的標的 |
    | **最新 YoY (%)** | 本月 vs 去年同月營收成長率 |
    | **加速斜率** | 數字越大，成長越加速 |
    | **連3月正成長** | 是否連續 3 個月都在正成長 |
    | **成長加速中** | 成長速度是否還在加快 |
    | **毛利率狀態** | 需 FinMind Token，偵測做帳風險 |

    ### ⚙️ 參數建議值
    | 參數 | 建議值 | 說明 |
    |------|--------|------|
    | 回溯月數 | 5～6 | 越多越準，速度較慢 |
    | 最低 YoY | 10～20% | 越高候選越少但品質更好 |
    | 最低加速斜率 | 0～2 | 0 = 只要有加速即可 |
    | 毛利率警戒線 | 10% | 低於此值標記⚠️ |
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
    if not run_btn:
        st.markdown("""
        <div style="text-align:center;padding:70px 0;color:#506880;">
            <div style="font-size:56px">🐋</div>
            <p style="font-size:18px;margin-top:16px;">點左上角「>」展開設定，再按「開始分析」</p>
            <p style="font-size:12px;">首次執行約 1～2 分鐘</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        history = build_history(months=months_back)
        if history.empty:
            st.error("❌ 資料抓取失敗，請稍後再試。")
            st.stop()

        total_stocks = history["stock_id"].nunique()
        st.success(f"✅ 載入 {len(history):,} 筆記錄，共 {total_stocks:,} 支股票")

        with st.spinner("⚙️ 執行成長動能篩選..."):
            candidates = run_growth_scanner(history)

        if not candidates.empty:
            candidates = candidates[
                (candidates["最新YoY(%)"] >= min_yoy) &
                (candidates["加速斜率"]   >= min_slope)
            ]

        if token_to_use and not candidates.empty:
            candidates = run_fake_detector(
                candidates, token_to_use, margin_threshold
            )

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
        c3.metric("⚠️ 毛利率異常", f"{flagged}" if token_to_use else "未偵測")
        c4.metric("✅ 最終候選",    f"{passed - flagged}")
        st.divider()

        if candidates.empty:
            st.markdown("""
            <div class="alert-yellow">
                目前無股票通過所有條件，可試著調低 YoY 門檻或縮短回溯月數。
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
                        if "毛利率狀態" in display_cols
                        else []
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
