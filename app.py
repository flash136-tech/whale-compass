# ════════════════════════════════════════════════════════════
#  大戶思維投資導航系統 — Streamlit Cloud 版 v1.4
#  資料來源：MOPS 公開資訊觀測站（完全免費，不需 Token）
# ════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import urllib3
from datetime import datetime, timedelta
import time
import io

# 關掉 SSL 警告訊息（因為 MOPS 憑證問題）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
</style>
""", unsafe_allow_html=True)

MOPS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer":    "https://mops.twse.com.tw/mops/web/t05st10_ifrs",
    "Accept":     "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ════════════════════════════════════════════════════════════
#  MOPS 月營收抓取（requests + BeautifulSoup）
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def fetch_revenue_mops(year: int, month: int) -> pd.DataFrame:
    """
    用 requests + BeautifulSoup 抓取 MOPS 月營收頁面。
    比 pd.read_html 更穩定，能正確處理 Big5 編碼。
    """
    roc_year = year - 1911
    url = (
        f"https://mops.twse.com.tw/nas/t21/sii/"
        f"t21sc03_{roc_year}_{month}_0.html"
    )

    try:
        resp = requests.get(
            url,
            headers=MOPS_HEADERS,
            verify=False,
            timeout=20,
        )
        resp.encoding = "big5"
        html_text = resp.text

        if "查無資料" in html_text or len(html_text) < 500:
            return pd.DataFrame()

        soup   = BeautifulSoup(html_text, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 5:
                continue

            parsed = []
            for row in rows:
                cells = row.find_all(["td", "th"])
                parsed.append([c.get_text(strip=True) for c in cells])

            if not parsed:
                continue

            # 找到有「公司代號」的那一列當表頭
            header_idx = None
            for i, row in enumerate(parsed):
                if any("代號" in c or "代碼" in c for c in row):
                    header_idx = i
                    break

            if header_idx is None:
                continue

            headers = parsed[header_idx]
            data    = parsed[header_idx + 1:]

            if not data:
                continue

            df = pd.DataFrame(data, columns=headers[:len(data[0])]
                              if len(headers) >= len(data[0]) else None)

            # 尋找關鍵欄位
            col_map = {}
            for c in df.columns:
                cs = str(c)
                if "代號" in cs or "代碼" in cs:
                    col_map[c] = "stock_id"
                elif "名稱" in cs:
                    col_map[c] = "name"
                elif "當月營收" in cs:
                    col_map[c] = "revenue"
                elif "去年同月" in cs and "增減" in cs:
                    col_map[c] = "yoy_pct"

            if "stock_id" not in col_map.values():
                continue
            if "revenue" not in col_map.values():
                continue

            df = df.rename(columns=col_map)
            keep = [v for v in ["stock_id", "name", "revenue", "yoy_pct"]
                    if v in df.columns]
            df = df[keep].copy()

            df["year_month"] = f"{year}-{month:02d}"
            df["revenue"]    = pd.to_numeric(
                df["revenue"].str.replace(",", ""), errors="coerce"
            )
            if "yoy_pct" in df.columns:
                df["yoy_pct"] = pd.to_numeric(
                    df["yoy_pct"].str.replace(",", ""), errors="coerce"
                )
            df["stock_id"] = df["stock_id"].astype(str).str.strip()
            result = df.dropna(subset=["stock_id", "revenue"])
            result = result[result["stock_id"].str.match(r"^\d{4,6}$")]

            if len(result) > 10:
                return result

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
            bar.progress(
                (i + 1) / months,
                text=f"✅ 已載入 {dt.year}-{dt.month:02d}（{len(df)} 筆）"
            )
        else:
            bar.progress(
                (i + 1) / months,
                text=f"⚠️ {dt.year}-{dt.month:02d} 無資料（可能尚未公布）"
            )
        time.sleep(0.5)
    bar.empty()
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ════════════════════════════════════════════════════════════
#  FinMind 毛利率（選填，需 Token）
# ════════════════════════════════════════════════════════════

def get_finmind_token() -> str:
    try:
        return st.secrets["FINMIND_TOKEN"]
    except Exception:
        return ""


@st.cache_data(ttl=3600)
def fetch_gross_margin(stock_id: str, token: str):
    if not token:
        return None
    params = {
        "dataset":    "TaiwanStockFinancialStatements",
        "data_id":    stock_id,
        "start_date": "2023-01-01",
        "token":      token,
    }
    try:
        r   = requests.get(
            "https://api.finmindtrade.com/api/v4/data",
            params=params, timeout=10
        )
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
        grp = grp.drop_duplicates("year_month").tail(6).reset_index(drop=True)
        if len(grp) < 3:
            continue

        # YoY 欄位
        if "yoy_pct" not in grp.columns or grp["yoy_pct"].isna().sum() > 3:
            continue

        yoy   = grp["yoy_pct"].fillna(0).values
        slope = float(np.polyfit(range(len(yoy)), yoy, 1)[0])
        l3ok  = bool(all(v > 0 for v in yoy[-3:]))
        accel = slope > 0

        results.append({
            "股票代號":    str(sid),
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

    st.markdown("#### 📅 資料設定")
    months_back = st.slider("回溯月數", 3, 6, 5)

    st.markdown("#### 📈 成長門檻")
    min_yoy   = st.number_input("最低 YoY 成長率 (%)", value=10.0, step=5.0)
    min_slope = st.number_input("最低加速斜率", value=0.0, step=0.5)

    st.markdown("#### 🔍 做帳偵測（選填）")
    cloud_token = get_finmind_token()
    if cloud_token:
        st.success("✅ FinMind Token 已從雲端載入")
        token_to_use = cloud_token
    else:
        token_to_use = st.text_input(
            "FinMind Token（選填）",
            type="password",
            placeholder="有 Token 才啟用毛利率偵測",
        )

    margin_threshold = st.slider("毛利率警戒線 (%)", 1, 30, 10)

    st.divider()
    st.markdown("""
    <div style='font-size:11px;color:#506880;'>
    📡 資料來源：MOPS 公開資訊觀測站<br>
    🔍 做帳偵測：FinMind API（選填）<br>
    ⚠️ 本系統僅供研究參考，不構成投資建議
    </div>
    """, unsafe_allow_html=True)

    run_btn = st.button("🚀 開始分析", use_container_width=True, type="primary")


# ════════════════════════════════════════════════════════════
#  主畫面
# ════════════════════════════════════════════════════════════

st.title("🐋 大戶思維投資導航系統")
st.caption("Module 1 — 成長動能篩選器 ｜ v1.4（資料來源：MOPS，完全免費）")

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
    | **加速斜率** | 數字越大，成長加速越明顯 |
    | **連3月正成長** | 確認成長持續性 |
    | **成長加速中** | 確認趨勢走強，不是鈍化 |
    | **毛利率狀態** | 需 FinMind Token，偵測做帳風險 |

    ### ⚙️ 參數建議值
    | 參數 | 建議值 | 說明 |
    |------|--------|------|
    | 回溯月數 | 5～6 | 越多越準 |
    | 最低 YoY | 10～20% | 越高候選越精 |
    | 最低加速斜率 | 0～2 | 0 = 只要有加速 |
    | 毛利率警戒線 | 10% | 低於此值標記⚠️ |

    ### 💡 關於 FinMind Token
    做帳偵測功能需要 FinMind Token（個股查詢免費）。
    前往 [finmindtrade.com](https://finmindtrade.com) 免費註冊即可取得。
    """)

with tab_roadmap:
    st.markdown("""
    ### ✅ 已完成
    - Module 1：成長動能篩選器（MOPS，完全免費）
    - Module 1：做帳偵測（FinMind，個股查詢免費）
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
            <p style="font-size:18px;margin-top:16px;">點左上角「>」展開設定，按「開始分析」</p>
            <p style="font-size:12px;">資料來源：MOPS 公開資訊觀測站（免費）</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # 抓資料
        history = build_history(months=months_back)

        if history.empty:
            st.error("❌ 所有月份抓取失敗，MOPS 可能暫時無法連線，請稍後再試。")
            st.stop()

        total_stocks = history["stock_id"].nunique()
        st.markdown(f"""
        <div class="alert-green">
            ✅ 成功載入 <strong>{len(history):,}</strong> 筆記錄，
            共 <strong>{total_stocks:,}</strong> 支股票
        </div>
        """, unsafe_allow_html=True)

        # 套用用戶設定的 YoY 門檻（先在 scanner 裡處理）
        with st.spinner("⚙️ 執行成長動能篩選..."):
            candidates = run_growth_scanner(history)

        if not candidates.empty:
            candidates = candidates[
                (candidates["最新YoY(%)"] >= min_yoy) &
                (candidates["加速斜率"]   >= min_slope)
            ]

        # 做帳偵測
        if token_to_use and not candidates.empty:
            candidates = run_fake_detector(
                candidates, token_to_use, margin_threshold
            )

        # 統計
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
                            — {row['毛利率狀態']}，建議查核財報。
                        </div>
                        """, unsafe_allow_html=True)
