# 大戶思維投資導航系統 v2.5 - ETF持股管理（貼上自動解析）
import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import base64
import re
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="🐋 大戶思維投資導航",page_icon="🐋",layout="wide",initial_sidebar_state="expanded")
st.markdown("""<style>
.stApp{background-color:#0a0f1a;color:#c9d1d9;}
h1,h2,h3{color:#f0e070!important;}
.alert-red{background:#3a1010;border-left:4px solid #ff4444;padding:10px 14px;border-radius:4px;margin:6px 0;}
.alert-yellow{background:#2a1f00;border-left:4px solid #f0a500;padding:10px 14px;border-radius:4px;margin:6px 0;}
.alert-green{background:#0d2015;border-left:4px solid #56d364;padding:10px 14px;border-radius:4px;margin:6px 0;}
.alert-blue{background:#0a1e30;border-left:4px solid #4a9eff;padding:10px 14px;border-radius:4px;margin:6px 0;}
.alert-gold{background:#1a1000;border-left:4px solid #f0a500;padding:10px 14px;border-radius:4px;margin:6px 0;}
</style>""",unsafe_allow_html=True)

FINMIND_URL="https://api.finmindtrade.com/api/v4/data"
GITHUB_API="https://api.github.com"
WATCHLIST=list(dict.fromkeys(s for s in ["2330","2317","2454","2382","2308","2303","2881","2882","2891","2886","2884","2885","2892","2883","2887","1301","1303","1326","2002","2105","2207","2357","2379","2395","2408","2412","2474","2603","2609","2615","2801","3008","3045","3711","4904","4938","5871","5876","5880","6505","6669","8046","9910","2823","2880","2337","2344","2345","2376","2388","2449","2451","3034","3037","3081","3293","3443","3673","3680","3706","4961","4966","6415","6446","6464","6533","6550","6770","8069","2367","2385","2356","2360","2362","2377","2387","2392","2393","2397","2399","3017","3019","3105","3231","3532","4977","5269","6214","6239","6269","6278","6285","6289","6443","6449","6510","6531","6547","1101","1102","1216","1402","1605","2027","2049","2201","2204","2352","2371","2404","2849","3702","4912","5009","5274","6116","6176","9941","9945","1590","2610","2618"] if s.isdigit() and 4<=len(s)<=6))
INST_NAME_MAP={"Foreign_Investor":"外資","Investment_Trust":"投信","Dealer_self":"自營","Dealer_Hedging":"自營","Foreign_Dealer_Self":"外資"}

def parse_stock_ids(raw_text):
    """從任意格式文字自動解析台股代號"""
    if not raw_text.strip(): return []
    candidates=re.findall(r'\b(\d{4,6})\b',raw_text)
    valid=[]
    for c in candidates:
        if re.match(r'^20\d{2}$',c): continue
        if re.match(r'^19\d{2}$',c): continue
        if len(c)==4:
            if 1000<=int(c)<=9999: valid.append(c)
        elif len(c)==5:
            if 10000<=int(c)<=99999: valid.append(c)
    return list(dict.fromkeys(valid))

def get_token():
    try: return st.secrets["FINMIND_TOKEN"]
    except: return ""

def get_github_config():
    try: return {"token":st.secrets["GITHUB_TOKEN"],"repo":st.secrets["GITHUB_REPO"]}
    except: return None

def gh_get(repo,path,token):
    try:
        r=requests.get(f"{GITHUB_API}/repos/{repo}/contents/{path}",headers={"Authorization":f"token {token}","Accept":"application/vnd.github.v3+json"},timeout=10)
        if r.status_code==200:
            d=r.json(); return base64.b64decode(d["content"]).decode("utf-8"),d["sha"]
        return None,None
    except: return None,None

def gh_put(repo,path,content,token,sha=None,msg="update"):
    try:
        body={"message":msg,"content":base64.b64encode(content.encode()).decode()}
        if sha: body["sha"]=sha
        r=requests.put(f"{GITHUB_API}/repos/{repo}/contents/{path}",headers={"Authorization":f"token {token}","Accept":"application/vnd.github.v3+json"},json=body,timeout=15)
        return r.status_code in[200,201]
    except: return False

def load_etf_holdings(gh):
    if not gh: return {}
    c,_=gh_get(gh["repo"],"records/etf_holdings.json",gh["token"])
    if not c: return {}
    try: return json.loads(c)
    except: return {}

def save_etf_holdings(d,gh):
    if not gh: return False
    d["updated"]=datetime.today().strftime("%Y-%m-%d")
    c=json.dumps(d,ensure_ascii=False,indent=2)
    _,sha=gh_get(gh["repo"],"records/etf_holdings.json",gh["token"])
    return gh_put(gh["repo"],"records/etf_holdings.json",c,gh["token"],sha=sha,msg=f"ETF holdings {d['updated']}")

def save_results(m1,m2,cr,params,gh):
    if not gh: return False
    now=datetime.today()
    payload={"run_time":now.strftime("%Y-%m-%d %H:%M"),"run_month":now.strftime("%Y-%m"),"params":params,"m1_result":m1.to_dict(orient="records") if not m1.empty else [],"m2_result":m2.to_dict(orient="records") if not m2.empty else [],"cross_result":cr.to_dict(orient="records") if not cr.empty else []}
    c=json.dumps(payload,ensure_ascii=False,indent=2)
    _,sha=gh_get(gh["repo"],"records/latest.json",gh["token"])
    ok=gh_put(gh["repo"],"records/latest.json",c,gh["token"],sha=sha,msg=f"update {now.strftime('%Y-%m-%d')}")
    mp=f"records/{now.strftime('%Y-%m')}.json"
    ex,_=gh_get(gh["repo"],mp,gh["token"])
    if not ex: gh_put(gh["repo"],mp,c,gh["token"],msg=f"monthly {now.strftime('%Y-%m')}")
    return ok

def load_results(gh):
    if not gh: return None
    c,_=gh_get(gh["repo"],"records/latest.json",gh["token"])
    if not c: return None
    try: return json.loads(c)
    except: return None

def list_archives(gh):
    if not gh: return []
    try:
        r=requests.get(f"{GITHUB_API}/repos/{gh['repo']}/contents/records",headers={"Authorization":f"token {gh['token']}","Accept":"application/vnd.github.v3+json"},timeout=10)
        if r.status_code==200:
            return [f["name"].replace(".json","") for f in r.json() if f["name"] not in["latest.json","etf_holdings.json"] and f["name"].endswith(".json")]
        return []
    except: return []

@st.cache_data(ttl=86400)
def fetch_revenue(sid,start,token):
    try:
        r=requests.get(FINMIND_URL,params={"dataset":"TaiwanStockMonthRevenue","data_id":sid,"start_date":start,"token":token},timeout=10)
        d=r.json()
        if d.get("status")!=200: return pd.DataFrame()
        df=pd.DataFrame(d.get("data",[]))
        if df.empty: return df
        df["revenue"]=pd.to_numeric(df["revenue"],errors="coerce")
        df["year_month"]=df.apply(lambda r:f"{int(r['revenue_year'])}-{int(r['revenue_month']):02d}",axis=1)
        return df[["stock_id","revenue","revenue_year","revenue_month","year_month"]]
    except: return pd.DataFrame()

@st.cache_data(ttl=86400)
def fetch_name(sid,token):
    try:
        r=requests.get(FINMIND_URL,params={"dataset":"TaiwanStockInfo","data_id":sid,"token":token},timeout=8)
        d=r.json().get("data",[])
        if d: return d[0].get("stock_name","—")
    except: pass
    return "—"

@st.cache_data(ttl=86400)
def fetch_margin(sid,token):
    try:
        r=requests.get(FINMIND_URL,params={"dataset":"TaiwanStockFinancialStatements","data_id":sid,"start_date":"2023-01-01","token":token},timeout=10)
        df=pd.DataFrame(r.json().get("data",[]))
        if df.empty: return None
        gp=df[df["type"]=="GrossProfit"]["value"].values
        rev=df[df["type"]=="Revenue"]["value"].values
        if len(gp)>0 and len(rev)>0 and float(rev[-1])!=0: return round(float(gp[-1])/float(rev[-1])*100,2)
    except: pass
    return None

def scan_revenue(stocks,start,token):
    bar=st.progress(0,text="📡 M1：掃描月營收..."); frames=[]
    for i,sid in enumerate(stocks):
        df=fetch_revenue(sid,start,token)
        if not df.empty: frames.append(df)
        bar.progress((i+1)/len(stocks),text=f"📡 M1 {i+1}/{len(stocks)}：{sid}")
        if (i+1)%10==0: time.sleep(0.3)
    bar.empty()
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()

def calc_yoy(df):
    df=df.sort_values(["stock_id","revenue_year","revenue_month"])
    df["revenue_last_year"]=df.groupby(["stock_id","revenue_month"])["revenue"].shift(1)
    df["yoy_pct"]=((df["revenue"]-df["revenue_last_year"])/df["revenue_last_year"].abs()*100).round(2)
    return df.dropna(subset=["yoy_pct"])

def growth_scan(df,min_yoy,min_slope,months,token):
    cutoff=(datetime.today()-timedelta(days=30*months)).strftime("%Y-%m")
    df=df[df["year_month"]>=cutoff].sort_values(["stock_id","year_month"]); results=[]
    for sid,grp in df.groupby("stock_id"):
        grp=grp.drop_duplicates("year_month").tail(6).reset_index(drop=True)
        if len(grp)<3 or grp["yoy_pct"].isna().sum()>2: continue
        yoy=grp["yoy_pct"].fillna(0).values
        slope=float(np.polyfit(range(len(yoy)),yoy,1)[0])
        if not (all(v>min_yoy for v in yoy[-3:]) and slope>min_slope): continue
        results.append({"股票代號":str(sid),"公司名稱":"—","最新YoY(%)":round(float(yoy[-1]),1),"加速斜率":round(slope,2),"連3月正成長":"✅","成長加速中":"✅"})
    out=pd.DataFrame(results)
    if out.empty: return out
    for idx,row in out.iterrows():
        out.at[idx,"公司名稱"]=fetch_name(row["股票代號"],token); time.sleep(0.05)
    return out.sort_values("加速斜率",ascending=False).reset_index(drop=True)

def fake_detect(cands,token,thresh):
    if cands.empty: return cands
    risks=[]; bar=st.progress(0,text="🔍 M1：毛利率偵測..."); total=min(len(cands),20)
    for i,row in cands.head(total).iterrows():
        m=fetch_margin(str(row["股票代號"]),token)
        risks.append("—（無資料）" if m is None else f"⚠️ {m}%" if m<thresh else f"✅ {m}%")
        bar.progress((i+1)/total); time.sleep(0.1)
    bar.empty(); result=cands.head(total).copy(); result["毛利率狀態"]=risks
    return result

@st.cache_data(ttl=86400)
def fetch_inst(sid,start,token):
    try:
        r=requests.get(FINMIND_URL,params={"dataset":"TaiwanStockInstitutionalInvestorsBuySell","data_id":sid,"start_date":start,"token":token},timeout=10)
        d=r.json()
        if d.get("status")!=200: return pd.DataFrame()
        raw=pd.DataFrame(d.get("data",[]))
        if raw.empty: return pd.DataFrame()
        raw["date"]=pd.to_datetime(raw["date"])
        raw["buy"]=pd.to_numeric(raw["buy"],errors="coerce").fillna(0)
        raw["sell"]=pd.to_numeric(raw["sell"],errors="coerce").fillna(0)
        raw["net"]=raw["buy"]-raw["sell"]
        raw["類別"]=raw["name"].map(INST_NAME_MAP)
        raw=raw.dropna(subset=["類別"])
        daily=raw.groupby(["date","stock_id","類別"])["net"].sum().reset_index()
        pivot=daily.pivot_table(index=["date","stock_id"],columns="類別",values="net",aggfunc="sum").reset_index()
        pivot.columns.name=None
        for col in ["外資","投信","自營"]:
            if col not in pivot.columns: pivot[col]=0
            pivot[col]=pd.to_numeric(pivot[col],errors="coerce").fillna(0)
        pivot["外資買賣超(張)"]=(pivot["外資"]/1000).round(0)
        pivot["投信買賣超(張)"]=(pivot["投信"]/1000).round(0)
        pivot["自營買賣超(張)"]=(pivot["自營"]/1000).round(0)
        pivot["三大合計(張)"]=pivot["外資買賣超(張)"]+pivot["投信買賣超(張)"]+pivot["自營買賣超(張)"]
        pivot["stock_id"]=sid
        return pivot[["date","stock_id","外資買賣超(張)","投信買賣超(張)","自營買賣超(張)","三大合計(張)"]].sort_values("date")
    except: return pd.DataFrame()

def analyze_inst(sid,df,days):
    if df.empty: return {}
    recent=df.tail(days)
    if len(recent)==0: return {}
    consec=0
    for v in reversed(recent["三大合計(張)"].values):
        if v>0: consec+=1
        else: break
    buy_days=int((recent["三大合計(張)"]>0).sum()); total=len(recent)
    return {"stock_id":sid,"外資淨買(張)":round(recent["外資買賣超(張)"].sum(),0),"投信淨買(張)":round(recent["投信買賣超(張)"].sum(),0),"自營淨買(張)":round(recent["自營買賣超(張)"].sum(),0),"三大合計(張)":round(recent["三大合計(張)"].sum(),0),"連續買超天":consec,"買超天數":buy_days,"觀察天數":total,"買超比例":round(buy_days/total*100,1) if total>0 else 0}

def inst_scan(m1,start,token,min_c,min_r):
    if m1.empty: return pd.DataFrame()
    ids=m1["股票代號"].tolist(); total=len(ids)
    bar=st.progress(0,text=f"📊 M2：掃描 {total} 支候選法人動向..."); results=[]
    for i,sid in enumerate(ids):
        df=fetch_inst(sid,start,token)
        if not df.empty:
            s=analyze_inst(sid,df,days=20)
            if s and (s["連續買超天"]>=min_c or s["買超比例"]>=min_r): results.append(s)
        bar.progress((i+1)/total,text=f"📊 M2 {i+1}/{total}：{sid}"); time.sleep(0.2)
    bar.empty()
    if not results: return pd.DataFrame()
    out=pd.DataFrame(results)
    nm=dict(zip(m1["股票代號"],m1["公司名稱"]))
    out.insert(1,"公司名稱",out["stock_id"].map(nm).fillna("—"))
    def sl(row):
        if row["連續買超天"]>=5: return "🔥 強力買超"
        elif row["連續買超天"]>=3: return "✅ 持續買超"
        elif row["買超比例"]>=70: return "✅ 高頻買超"
        else: return "👀 值得觀察"
    out["信號強度"]=out.apply(sl,axis=1)
    return out.sort_values("連續買超天",ascending=False).reset_index(drop=True)

def cross(m1,m2):
    if m1.empty or m2.empty: return pd.DataFrame()
    common=set(m1["股票代號"])&set(m2["stock_id"])
    if not common: return pd.DataFrame()
    a=m1[m1["股票代號"].isin(common)].copy()
    b=m2[m2["stock_id"].isin(common)][["stock_id","三大合計(張)","連續買超天","買超比例","信號強度"]].rename(columns={"stock_id":"股票代號"})
    mg=a.merge(b,on="股票代號",how="inner")
    mg["綜合評分"]=(mg["加速斜率"]*0.5+mg["連續買超天"]*0.5).round(2)
    return mg.sort_values("綜合評分",ascending=False).reset_index(drop=True)

def hl(val):
    if "⚠️" in str(val): return "background:#3a1010;color:#ff6b6b"
    if "🔥" in str(val): return "background:#1a0d00;color:#f0a500"
    if "✅" in str(val): return "background:#0d2015;color:#56d364"
    if "👀" in str(val): return "background:#0a1e30;color:#4a9eff"
    return ""

# Sidebar
with st.sidebar:
    st.markdown("## 🐋 大戶思維\n#### 投資導航系統 v2.5")
    st.divider()
    ct=get_token()
    if ct: st.success("✅ FinMind Token 已載入"); tok=ct
    else:
        st.markdown("#### 🔑 FinMind Token（必填）")
        tok=st.text_input("貼上你的 Token",type="password",placeholder="finmindtrade.com 免費申請")
    gh=get_github_config()
    if gh: st.success("✅ GitHub 記憶系統已連接")
    else: st.warning("⚠️ GitHub Token 未設定")
    st.divider()
    st.markdown("#### 📅 Module 1")
    mb=st.slider("回溯月數",3,6,5)
    my=st.number_input("最低 YoY (%)",value=10.0,step=5.0)
    ms=st.number_input("最低加速斜率",value=0.0,step=0.5)
    mt=st.slider("毛利率警戒線 (%)",1,30,10)
    st.divider()
    st.markdown("#### 📊 Module 2")
    mc=st.slider("最低連續買超天",1,10,1)
    mr=st.slider("最低買超比例 (%)",20,90,40)
    st.divider()
    ci=st.text_input("自訂股票（選填）",placeholder="例：2330,6415")
    st.divider()
    st.caption("資料來源：FinMind Open API")
    st.caption("本系統僅供研究參考，不構成投資建議")
    run=st.button("🚀 重新分析",use_container_width=True,type="primary",disabled=not tok)

st.title("🐋 大戶思維投資導航系統")
st.caption("Module 1 成長動能 × Module 2-1 三大法人 ｜ v2.5")

t_cross,t_m1,t_m2,t_etf,t_hist,t_guide,t_road=st.tabs(["🎯 交叉比對","📈 Module 1","📊 Module 2","📋 ETF 持股管理","📅 歷史記錄","📖 使用說明","🗺 開發路線圖"])

# ETF 持股管理 Tab
with t_etf:
    st.subheader("📋 ETF 持股管理")
    st.markdown('<div class="alert-blue">從口袋證券複製持股頁面的全部文字，直接貼上即可。<br>系統自動找出所有股票代號，不需要整理格式。</div>',unsafe_allow_html=True)
    if not gh:
        st.markdown('<div class="alert-yellow">⚠️ 需要設定 GitHub Token 才能使用此功能。</div>',unsafe_allow_html=True)
    else:
        cur=load_etf_holdings(gh)
        c981=cur.get("00981A",[]); c992=cur.get("00992A",[]); upd=cur.get("updated","尚未設定")
        st.markdown(f'<div class="alert-green">📅 上次更新：<strong>{upd}</strong>　00981A：<strong>{len(c981)} 支</strong>　00992A：<strong>{len(c992)} 支</strong></div>',unsafe_allow_html=True)
        st.divider()

        st.markdown("### 📌 00981A 統一台股增長")
        st.markdown("1. 打開 [口袋證券 00981A 持股](https://www.pocket.tw/etf/tw/00981A/fundholding)\n2. 全選所有文字複製\n3. 貼到下方")
        r981=st.text_area("貼上 00981A 持股頁面文字",height=150,placeholder="把複製的全部文字貼這裡，格式不重要...",key="r981")
        if r981.strip():
            p981=parse_stock_ids(r981)
            if p981:
                st.markdown(f'<div class="alert-green">✅ 自動解析出 <strong>{len(p981)}</strong> 支股票代號</div>',unsafe_allow_html=True)
                st.code(", ".join(p981))
                new=set(p981)-set(c981); gone=set(c981)-set(p981)
                if new: st.markdown(f"🆕 **新增：** {', '.join(sorted(new))}")
                if gone: st.markdown(f"🗑️ **移除：** {', '.join(sorted(gone))}")
            else:
                st.markdown('<div class="alert-yellow">⚠️ 未找到有效股票代號。</div>',unsafe_allow_html=True)
                p981=c981
        else:
            p981=c981
            if c981: st.markdown(f"目前清單（{len(c981)} 支）：`{', '.join(c981[:10])}{'...' if len(c981)>10 else ''}`")

        st.divider()
        st.markdown("### 📌 00992A 群益科技創新")
        st.markdown("1. 打開 [口袋證券 00992A 持股](https://www.pocket.tw/etf/tw/00992A/fundholding)\n2. 全選所有文字複製\n3. 貼到下方")
        r992=st.text_area("貼上 00992A 持股頁面文字",height=150,placeholder="把複製的全部文字貼這裡，格式不重要...",key="r992")
        if r992.strip():
            p992=parse_stock_ids(r992)
            if p992:
                st.markdown(f'<div class="alert-green">✅ 自動解析出 <strong>{len(p992)}</strong> 支股票代號</div>',unsafe_allow_html=True)
                st.code(", ".join(p992))
                new=set(p992)-set(c992); gone=set(c992)-set(p992)
                if new: st.markdown(f"🆕 **新增：** {', '.join(sorted(new))}")
                if gone: st.markdown(f"🗑️ **移除：** {', '.join(sorted(gone))}")
            else:
                st.markdown('<div class="alert-yellow">⚠️ 未找到有效股票代號。</div>',unsafe_allow_html=True)
                p992=c992
        else:
            p992=c992
            if c992: st.markdown(f"目前清單（{len(c992)} 支）：`{', '.join(c992[:10])}{'...' if len(c992)>10 else ''}`")

        st.divider()
        has_changes=(r981.strip() and p981) or (r992.strip() and p992)
        if st.button("💾 儲存 ETF 持股清單到 GitHub",type="primary",use_container_width=True,disabled=not has_changes):
            with st.spinner("💾 儲存中..."):
                ok=save_etf_holdings({"00981A":p981,"00992A":p992},gh)
            if ok:
                st.markdown(f'<div class="alert-green">✅ 儲存成功！00981A：{len(p981)} 支　00992A：{len(p992)} 支<br>下次「🚀 重新分析」時會自動整合這份清單。</div>',unsafe_allow_html=True)
                st.balloons()
            else:
                st.markdown('<div class="alert-red">❌ 儲存失敗，請確認 GitHub Token 是否正確。</div>',unsafe_allow_html=True)

        if c981 or c992:
            st.divider()
            st.markdown("### 📊 下次分析的掃描範圍預覽")
            all_etf=list(dict.fromkeys(c981+c992))
            combined=list(dict.fromkeys(WATCHLIST+all_etf))
            etf_only=[s for s in all_etf if s not in WATCHLIST]
            c1,c2,c3=st.columns(3)
            c1.metric("固定清單",f"{len(WATCHLIST)} 支")
            c2.metric("ETF 新增",f"{len(etf_only)} 支")
            c3.metric("合計掃描",f"{len(combined)} 支")
            if etf_only:
                st.markdown("**ETF 額外補充（不在固定清單內）：**")
                st.code(", ".join(etf_only))

with t_guide:
    st.markdown("""
### 📱 操作方式（v2.5）
1. 每月 10 日：先到「📋 ETF 持股管理」更新持股清單
2. 再按左側「🚀 重新分析」
3. 優先看「🎯 交叉比對」Tab

### 📋 ETF 持股更新（約 3 分鐘）
1. 打開口袋證券查 00981A / 00992A 持股頁面
2. 全選所有文字 → 複製
3. 貼到文字框 → 系統自動解析代號
4. 確認後按「💾 儲存」

### 💡 建議節奏
- **每月 10 日後**：更新 ETF 持股 → 重新分析
- **其他時間**：直接開 app 看上次結果
""")

with t_road:
    st.markdown("""
### ✅ 已完成
- Module 1：成長動能篩選 + 做帳偵測
- Module 2-1：三大法人買賣超
- M1 × M2 交叉比對
- GitHub 記憶系統
- **v2.5：ETF 持股管理（貼上自動解析）** ← 新增

### 🔄 規劃中
- Module 2-2：抗跌強勢偵測
- Module 2-3：發動點偵測
- Module 3：政策 NLP
- Module 4：停損紀律控制台
""")

# 主分析
if not tok:
    with t_cross:
        st.markdown('<div class="alert-blue"><strong>🔑 請先在左側輸入 FinMind Token</strong></div>',unsafe_allow_html=True)
else:
    cached=None
    if not run and gh:
        with st.spinner("📂 載入上次結果..."): cached=load_results(gh)

    if cached and not run:
        rt=cached.get("run_time","未知")
        m1r=pd.DataFrame(cached.get("m1_result",[])); m2r=pd.DataFrame(cached.get("m2_result",[])); crr=pd.DataFrame(cached.get("cross_result",[]))
        st.info(f"📂 上次分析結果（{rt}）｜按「🚀 重新分析」更新")
        with t_m1:
            st.subheader("📈 Module 1"); st.markdown(f'<div class="alert-blue">📂 快取（{rt}）</div>',unsafe_allow_html=True)
            if not m1r.empty:
                dc=[c for c in ["股票代號","公司名稱","最新YoY(%)","加速斜率","連3月正成長","成長加速中","毛利率狀態"] if c in m1r.columns]
                fmt={k:v for k,v in {"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}"}.items() if k in m1r.columns}
                st.dataframe(m1r[dc].style.map(hl,subset=["毛利率狀態"] if "毛利率狀態" in dc else []).format(fmt),use_container_width=True,height=400)
                st.download_button("📥 下載 M1 CSV",data=m1r[dc].to_csv(index=False,encoding="utf-8-sig"),file_name=f"m1_{rt[:7]}.csv",mime="text/csv")
        with t_m2:
            st.subheader("📊 Module 2"); st.markdown(f'<div class="alert-blue">📂 快取（{rt}）</div>',unsafe_allow_html=True)
            if not m2r.empty:
                mc=[c for c in ["stock_id","公司名稱","三大合計(張)","外資淨買(張)","投信淨買(張)","連續買超天","買超比例","信號強度"] if c in m2r.columns]
                st.dataframe(m2r[mc].style.map(hl,subset=["信號強度"] if "信號強度" in m2r.columns else []),use_container_width=True,height=400)
        with t_cross:
            st.subheader("🎯 交叉比對"); st.markdown('<div class="alert-gold"><strong>業績加速成長（M1）＋ 三大法人持續買超（M2）= 雙重確認最強訊號</strong></div>',unsafe_allow_html=True)
            st.markdown(f'<div class="alert-blue">📂 快取（{rt}）</div>',unsafe_allow_html=True)
            if crr.empty:
                st.markdown('<div class="alert-yellow">上次無交叉比對結果。</div>',unsafe_allow_html=True)
                if not m1r.empty:
                    dc=[c for c in ["股票代號","公司名稱","最新YoY(%)","加速斜率"] if c in m1r.columns]
                    st.dataframe(m1r[dc],use_container_width=True,height=320)
            else:
                c1,c2,c3,c4=st.columns(4)
                c1.metric("M1 候選",f"{len(m1r)}"); c2.metric("M2 通過",f"{len(m2r)}"); c3.metric("🎯 命中",f"{len(crr)}")
                if "綜合評分" in crr.columns: c4.metric("最高評分",f"{crr['綜合評分'].max():.2f}")
                cc=["股票代號","公司名稱","最新YoY(%)","加速斜率","三大合計(張)","連續買超天","買超比例","信號強度","綜合評分"]
                if "毛利率狀態" in crr.columns: cc.insert(4,"毛利率狀態")
                cc=[c for c in cc if c in crr.columns]
                fmt={k:v for k,v in {"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}","三大合計(張)":"{:.0f}","買超比例":"{:.1f}%","綜合評分":"{:.2f}"}.items() if k in crr.columns}
                st.dataframe(crr[cc].style.map(hl,subset=[c for c in ["信號強度","毛利率狀態"] if c in cc]).format(fmt),use_container_width=True,height=420)
                st.download_button("📥 下載交叉比對 CSV",data=crr[cc].to_csv(index=False,encoding="utf-8-sig"),file_name=f"cross_{rt[:7]}.csv",mime="text/csv")
                st.divider(); st.markdown("#### 📋 各標的重點提示")
                for _,row in crr.iterrows():
                    warn="⚠️" in str(row.get("毛利率狀態",""))
                    st.markdown(f'<div class="{"alert-red" if warn else "alert-green"}"><strong>{row.get("股票代號","")} {row.get("公司名稱","")}</strong> ｜ YoY <strong>{row.get("最新YoY(%)",0):.1f}%</strong> ｜ 連買 <strong>{int(row.get("連續買超天",0))}</strong> 天 ｜ {row.get("信號強度","")}{"｜ ⚠️ 毛利率需注意" if warn else ""}</div>',unsafe_allow_html=True)

    elif run or not cached:
        if not cached and not run:
            with t_cross:
                st.markdown('<div style="text-align:center;padding:60px 0;color:#506880;"><div style="font-size:56px">🐋</div><p style="font-size:18px;margin-top:16px;">尚無歷史記錄，請按左側「🚀 重新分析」</p></div>',unsafe_allow_html=True)
            st.stop()

        # 整合 ETF 持股
        scan=WATCHLIST.copy()
        if gh:
            eh=load_etf_holdings(gh)
            e981=eh.get("00981A",[]); e992=eh.get("00992A",[])
            all_etf=list(dict.fromkeys(e981+e992))
            scan=list(dict.fromkeys(scan+all_etf))
            added=len([s for s in all_etf if s not in WATCHLIST])
            if added>0: st.info(f"✅ 已整合 ETF 持股：00981A（{len(e981)}支）+ 00992A（{len(e992)}支），新增 {added} 支，合計掃描 {len(scan)} 支")
        if ci.strip():
            extras=[s.strip() for s in ci.split(",") if s.strip().isdigit() and 4<=len(s.strip())<=6]
            scan=list(dict.fromkeys(scan+extras))

        m1s=(datetime.today()-timedelta(days=30*(mb+13))).strftime("%Y-%m-%d")
        m2s=(datetime.today()-timedelta(days=35)).strftime("%Y-%m-%d")

        with t_m1:
            st.subheader("📈 Module 1 — 成長動能篩選")
            raw=scan_revenue(scan,m1s,tok)
            if raw.empty: st.error("❌ 月營收資料抓取失敗。"); st.stop()
            yoy=calc_yoy(raw); scanned=yoy["stock_id"].nunique()
            st.success(f"✅ 成功取得 {scanned} 支股票營收資料")
            with st.spinner("⚙️ 執行成長動能篩選..."): m1r=growth_scan(yoy,my,ms,mb,tok)
            if not m1r.empty: m1r=fake_detect(m1r,tok,mt)
            c1,c2,c3,c4=st.columns(4)
            passed=len(m1r); flagged=len(m1r[m1r["毛利率狀態"].str.contains("⚠️",na=False)]) if "毛利率狀態" in m1r.columns else 0
            c1.metric("掃描股票數",f"{scanned}"); c2.metric("通過成長篩選",f"{passed}"); c3.metric("⚠️ 毛利率異常",f"{flagged}"); c4.metric("✅ M1 最終候選",f"{passed-flagged}")
            if m1r.empty: st.markdown('<div class="alert-yellow">無股票通過 M1 條件，請調低 YoY 門檻。</div>',unsafe_allow_html=True)
            else:
                dc=["股票代號","公司名稱","最新YoY(%)","加速斜率","連3月正成長","成長加速中"]
                if "毛利率狀態" in m1r.columns: dc.append("毛利率狀態")
                st.dataframe(m1r[dc].style.map(hl,subset=["毛利率狀態"] if "毛利率狀態" in dc else []).format({"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}"}).background_gradient(subset=["加速斜率"],cmap="YlGn"),use_container_width=True,height=400)
                st.download_button("📥 下載 M1 CSV",data=m1r[dc].to_csv(index=False,encoding="utf-8-sig"),file_name=f"m1_{datetime.today().strftime('%Y%m%d')}.csv",mime="text/csv")

        with t_m2:
            st.subheader("📊 Module 2-1 — 三大法人買賣超")
            m1c=len(m1r) if 'm1r' in dir() else 0
            st.markdown(f'<div class="alert-green">✅ 只針對 M1 篩出的 <strong>{m1c} 支候選</strong>做法人追蹤</div>',unsafe_allow_html=True)
            if 'm1r' not in dir() or m1r.empty: st.warning("請先完成 Module 1。"); m2r=pd.DataFrame()
            else:
                m2r=inst_scan(m1r,m2s,tok,mc,mr)
                if m2r.empty: st.markdown('<div class="alert-yellow">M1 候選中目前無股票符合法人買超條件。</div>',unsafe_allow_html=True)
                else:
                    c1,c2,c3=st.columns(3)
                    strong=len(m2r[m2r["信號強度"].str.contains("🔥")]); steady=len(m2r[m2r["信號強度"].str.contains("✅")])
                    c1.metric("通過 M2",f"{len(m2r)}"); c2.metric("🔥 強力",f"{strong}"); c3.metric("✅ 持續",f"{steady}")
                    m2c=[c for c in ["stock_id","公司名稱","三大合計(張)","外資淨買(張)","投信淨買(張)","自營淨買(張)","連續買超天","買超比例","信號強度"] if c in m2r.columns]
                    st.dataframe(m2r[m2c].style.map(hl,subset=["信號強度"]).format({"買超比例":"{:.1f}%","三大合計(張)":"{:.0f}","外資淨買(張)":"{:.0f}","投信淨買(張)":"{:.0f}","自營淨買(張)":"{:.0f}"}).background_gradient(subset=["連續買超天"],cmap="YlGn"),use_container_width=True,height=400)
                    st.download_button("📥 下載 M2 CSV",data=m2r[m2c].to_csv(index=False,encoding="utf-8-sig"),file_name=f"m2_{datetime.today().strftime('%Y%m%d')}.csv",mime="text/csv")

        with t_cross:
            st.subheader("🎯 交叉比對 — M1 × M2 最強訊號")
            st.markdown('<div class="alert-gold"><strong>業績加速成長（M1）＋ 三大法人持續買超（M2）= 雙重確認最強訊號</strong></div>',unsafe_allow_html=True)
            crr=pd.DataFrame()
            m1ok='m1r' in dir() and not m1r.empty; m2ok='m2r' in dir() and not m2r.empty
            if m1ok and m2ok: crr=cross(m1r,m2r)
            if not m1ok: st.info("請先執行分析。")
            elif not m2ok or crr.empty:
                st.markdown('<div class="alert-yellow">目前無股票同時通過 M1 和 M2。M1 候選名單供參考：</div>',unsafe_allow_html=True)
                if m1ok:
                    dc=[c for c in ["股票代號","公司名稱","最新YoY(%)","加速斜率","毛利率狀態"] if c in m1r.columns]
                    st.dataframe(m1r[dc],use_container_width=True,height=320)
            else:
                c1,c2,c3,c4=st.columns(4)
                c1.metric("M1 候選",f"{len(m1r)}"); c2.metric("M2 通過",f"{len(m2r)}"); c3.metric("🎯 命中",f"{len(crr)}")
                if "綜合評分" in crr.columns: c4.metric("最高評分",f"{crr['綜合評分'].max():.2f}")
                st.divider()
                cc=["股票代號","公司名稱","最新YoY(%)","加速斜率","三大合計(張)","連續買超天","買超比例","信號強度","綜合評分"]
                if "毛利率狀態" in crr.columns: cc.insert(4,"毛利率狀態")
                cc=[c for c in cc if c in crr.columns]
                fmt={k:v for k,v in {"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}","三大合計(張)":"{:.0f}","買超比例":"{:.1f}%","綜合評分":"{:.2f}"}.items() if k in crr.columns}
                st.dataframe(crr[cc].style.map(hl,subset=[c for c in ["信號強度","毛利率狀態"] if c in cc]).format(fmt).background_gradient(subset=["綜合評分"],cmap="YlOrRd"),use_container_width=True,height=420)
                st.download_button("📥 下載交叉比對 CSV",data=crr[cc].to_csv(index=False,encoding="utf-8-sig"),file_name=f"cross_{datetime.today().strftime('%Y%m%d')}.csv",mime="text/csv")
                st.divider(); st.markdown("#### 📋 各標的重點提示")
                for _,row in crr.iterrows():
                    warn="⚠️" in str(row.get("毛利率狀態",""))
                    st.markdown(f'<div class="{"alert-red" if warn else "alert-green"}"><strong>{row["股票代號"]} {row["公司名稱"]}</strong> ｜ YoY <strong>{row["最新YoY(%)"]:.1f}%</strong> ｜ 連買 <strong>{int(row["連續買超天"])}</strong> 天 ｜ {row.get("信號強度","")}{"｜ ⚠️ 毛利率需注意" if warn else ""}</div>',unsafe_allow_html=True)

        if gh and 'm1r' in dir():
            params={"months_back":mb,"min_yoy":my,"min_slope":ms,"margin_threshold":mt,"min_consec":mc,"min_buy_ratio":mr}
            m2sv=m2r if 'm2r' in dir() else pd.DataFrame(); crsv=crr if 'crr' in dir() else pd.DataFrame()
            with st.spinner("💾 自動存檔到 GitHub..."):
                ok=save_results(m1r,m2sv,crsv,params,gh)
            if ok: st.toast("✅ 結果已自動存到 GitHub！")
            else: st.toast("⚠️ 存檔失敗，請確認 GitHub Token。")

with t_hist:
    st.subheader("📅 歷史分析記錄")
    if not gh: st.markdown('<div class="alert-blue">需要設定 GitHub Token 才能查看。</div>',unsafe_allow_html=True)
    else:
        archives=list_archives(gh)
        if not archives: st.markdown('<div class="alert-yellow">尚無歷史記錄。</div>',unsafe_allow_html=True)
        else:
            sel=st.selectbox("選擇月份",sorted(archives,reverse=True))
            if sel:
                c,_=gh_get(gh["repo"],f"records/{sel}.json",gh["token"])
                if c:
                    d=json.loads(c); st.markdown(f"**分析時間：** {d.get('run_time','—')}")
                    hc=pd.DataFrame(d.get("cross_result",[]))
                    if not hc.empty:
                        sc=[c for c in ["股票代號","公司名稱","最新YoY(%)","加速斜率","連續買超天","信號強度","綜合評分"] if c in hc.columns]
                        st.dataframe(hc[sc],use_container_width=True,height=300)
