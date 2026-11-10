# 大戶思維投資導航系統 v2.7 - 超跌/PEG/ROE/RSI/融資率 五層篩選精選5檔
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
            return [f["name"].replace(".json","") for f in r.json() if f["name"] not in["latest.json","etf_holdings.json","watchlist.json"] and f["name"].endswith(".json")]
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
def fetch_financials(sid,token):
    """抓財報：毛利率 + ROE"""
    try:
        r=requests.get(FINMIND_URL,params={"dataset":"TaiwanStockFinancialStatements","data_id":sid,"start_date":"2023-01-01","token":token},timeout=10)
        df=pd.DataFrame(r.json().get("data",[]))
        if df.empty: return None,None
        # 毛利率
        gross_margin=None
        gp=df[df["type"]=="GrossProfit"]["value"].values
        rev=df[df["type"]=="Revenue"]["value"].values
        if len(gp)>0 and len(rev)>0 and float(rev[-1])!=0:
            gross_margin=round(float(gp[-1])/float(rev[-1])*100,2)
        # ROE：NetIncome / TotalEquity
        roe=None
        ni_rows=df[df["type"].isin(["NetIncome","ProfitLoss","NetIncomeAttributableToOwnersOfParent"])]
        eq_rows=df[df["type"].isin(["TotalEquityAttributableToOwnersOfParent","StockholdersEquity","Equity","TotalEquity"])]
        if not ni_rows.empty and not eq_rows.empty:
            latest_ni=float(ni_rows.sort_values("date").iloc[-1]["value"])
            latest_eq=float(eq_rows.sort_values("date").iloc[-1]["value"])
            if latest_eq>0: roe=round(latest_ni/latest_eq*100,1)
        return gross_margin,roe
    except: return None,None

# 保留舊函式名稱供 fake_detect 使用
@st.cache_data(ttl=86400)
def fetch_margin(sid,token):
    gm,_=fetch_financials(sid,token)
    return gm

@st.cache_data(ttl=3600)
def fetch_per(sid,token):
    """抓最新 PER / PBR"""
    try:
        start=(datetime.today()-timedelta(days=5)).strftime("%Y-%m-%d")
        r=requests.get(FINMIND_URL,params={"dataset":"TaiwanStockPER","data_id":sid,"start_date":start,"token":token},timeout=10)
        data=r.json()
        if data.get("status")!=200: return None,None
        df=pd.DataFrame(data.get("data",[]))
        if df.empty: return None,None
        df=df.sort_values("date")
        latest=df.iloc[-1]
        per=round(float(latest["PER"]),1) if latest["PER"] else None
        pbr=round(float(latest["PBR"]),1) if latest["PBR"] else None
        return per,pbr
    except: return None,None

@st.cache_data(ttl=86400)
def fetch_per_hist(sid,token):
    """抓2年歷史PER → 中位數 → 與現值折溢價"""
    try:
        start=(datetime.today()-timedelta(days=730)).strftime("%Y-%m-%d")
        r=requests.get(FINMIND_URL,params={"dataset":"TaiwanStockPER","data_id":sid,"start_date":start,"token":token},timeout=15)
        data=r.json()
        if data.get("status")!=200: return None,None
        df=pd.DataFrame(data.get("data",[]))
        if df.empty: return None,None
        df=df.sort_values("date")
        df["PER"]=pd.to_numeric(df["PER"],errors="coerce")
        df=df.dropna(subset=["PER"])
        df=df[df["PER"]>0]
        if len(df)<20: return None,None
        current_per=float(df.iloc[-1]["PER"])
        hist_med=float(df["PER"].median())
        if hist_med<=0 or current_per<=0: return None,None
        # 折價% > 0 表示目前PER低於歷史中位（相對便宜）
        discount=round((hist_med-current_per)/hist_med*100,1)
        return round(hist_med,1),discount
    except: return None,None

@st.cache_data(ttl=3600)
def fetch_rsi(sid,token):
    """抓日線計算 RSI-14"""
    try:
        start=(datetime.today()-timedelta(days=90)).strftime("%Y-%m-%d")
        r=requests.get(FINMIND_URL,params={"dataset":"TaiwanStockPrice","data_id":sid,"start_date":start,"token":token},timeout=10)
        df=pd.DataFrame(r.json().get("data",[]))
        if df.empty or len(df)<15: return None
        df=df.sort_values("date")
        closes=pd.to_numeric(df["close"],errors="coerce").dropna().values
        if len(closes)<15: return None
        deltas=np.diff(closes)
        gains=np.where(deltas>0,deltas,0.0)
        losses=np.where(deltas<0,-deltas,0.0)
        period=14
        avg_gain=float(np.mean(gains[:period]))
        avg_loss=float(np.mean(losses[:period]))
        for i in range(period,len(gains)):
            avg_gain=(avg_gain*(period-1)+gains[i])/period
            avg_loss=(avg_loss*(period-1)+losses[i])/period
        if avg_loss==0: return 100.0
        rs=avg_gain/avg_loss
        return round(100-(100/(1+rs)),1)
    except: return None

@st.cache_data(ttl=3600)
def fetch_margin_ratio(sid,token):
    """抓融資使用率（%）"""
    try:
        start=(datetime.today()-timedelta(days=10)).strftime("%Y-%m-%d")
        r=requests.get(FINMIND_URL,params={"dataset":"TaiwanStockMarginPurchaseShortsale","data_id":sid,"start_date":start,"token":token},timeout=10)
        df=pd.DataFrame(r.json().get("data",[]))
        if df.empty: return None
        df=df.sort_values("date")
        latest=df.iloc[-1]
        # 嘗試直接欄位
        for col in["MarginPurchaseRatio","margin_purchase_ratio"]:
            if col in df.columns:
                v=latest.get(col)
                if v is not None and str(v) not in["","nan","None"]:
                    return round(float(v),1)
        # 計算：餘額/限額
        for b_col,l_col in[("MarginPurchaseBalance","MarginPurchaseLimit"),
                            ("margin_purchase_balance","margin_purchase_limit")]:
            if b_col in df.columns and l_col in df.columns:
                bal=latest.get(b_col); lim=latest.get(l_col)
                if bal and lim and float(lim)>0:
                    return round(float(bal)/float(lim)*100,1)
        return None
    except: return None

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

def cross(m1,m2,token=""):
    if m1.empty or m2.empty: return pd.DataFrame()
    common=set(m1["股票代號"])&set(m2["stock_id"])
    if not common: return pd.DataFrame()
    a=m1[m1["股票代號"].isin(common)].copy()
    b=m2[m2["stock_id"].isin(common)][["stock_id","三大合計(張)","連續買超天","買超比例","信號強度"]].rename(columns={"stock_id":"股票代號"})
    mg=a.merge(b,on="股票代號",how="inner")
    mg["綜合評分"]=(mg["加速斜率"]*0.5+mg["連續買超天"]*0.5).round(2)
    if token:
        per_list,est_per_list,pbr_list=[],[],[]
        bar=st.progress(0,text="📊 抓取本益比資料...")
        total=len(mg)
        for i,row in mg.iterrows():
            per,pbr=fetch_per(str(row["股票代號"]),token)
            per_list.append(per); pbr_list.append(pbr)
            if per and row["最新YoY(%)"]>0:
                est=round(per/(1+row["最新YoY(%)"]/100),1)
            else: est=None
            est_per_list.append(est)
            bar.progress((i-mg.index[0]+1)/total); time.sleep(0.1)
        bar.empty()
        mg["目前PER"]=per_list; mg["預估PER"]=est_per_list; mg["PBR"]=pbr_list
    return mg.sort_values("綜合評分",ascending=False).reset_index(drop=True)

def enrich_cross(crr,tok):
    """v2.7 深度估值層：為交叉比對結果新增 PEG、折價%、ROE、RSI、融資率"""
    if crr.empty: return crr
    total=len(crr)
    bar=st.progress(0,text="🔬 深度估值分析（超跌/ROE/RSI/融資）...")
    peg_l,hist_per_l,discount_l,roe_l,rsi_l,mr_l=[],[],[],[],[],[]
    for idx,(i,row) in enumerate(crr.iterrows()):
        sid=str(row["股票代號"])
        # PEG = 目前PER / YoY%（已有資料，不需額外 API）
        per=row.get("目前PER",None); yoy=float(row.get("最新YoY(%)",0) or 0)
        peg=round(float(per)/yoy,2) if per and yoy>0 else None
        peg_l.append(peg)
        # 歷史PER中位 & 折價%
        hist_med,discount=fetch_per_hist(sid,tok)
        hist_per_l.append(hist_med); discount_l.append(discount)
        # ROE
        _,roe=fetch_financials(sid,tok)
        roe_l.append(roe)
        # RSI-14
        rsi=fetch_rsi(sid,tok)
        rsi_l.append(rsi)
        # 融資使用率
        mr=fetch_margin_ratio(sid,tok)
        mr_l.append(mr)
        bar.progress((idx+1)/total,text="🔬 深度分析 {}/{}：{}".format(idx+1,total,sid))
        time.sleep(0.15)
    bar.empty()
    out=crr.copy()
    out["PEG"]=peg_l; out["歷史PER中位"]=hist_per_l; out["折價%"]=discount_l
    out["ROE%"]=roe_l; out["RSI"]=rsi_l; out["融資率%"]=mr_l
    return out

def hl(val):
    if "⚠️" in str(val): return "background:#3a1010;color:#ff6b6b"
    if "🔥" in str(val): return "background:#1a0d00;color:#f0a500"
    if "✅" in str(val): return "background:#0d2015;color:#56d364"
    if "👀" in str(val): return "background:#0a1e30;color:#4a9eff"
    return ""

# ── 追蹤清單 GitHub 存讀 ─────────────────────────────────────────────────────
def load_watchlist(gh):
    if not gh: return []
    c,_=gh_get(gh["repo"],"records/watchlist.json",gh["token"])
    if not c: return []
    try: return json.loads(c)
    except: return []

def save_watchlist(items,gh):
    if not gh: return False
    c=json.dumps(items,ensure_ascii=False,indent=2)
    _,sha=gh_get(gh["repo"],"records/watchlist.json",gh["token"])
    return gh_put(gh["repo"],"records/watchlist.json",c,gh["token"],sha=sha,msg="watchlist {}".format(datetime.today().strftime("%Y-%m-%d")))

# ── v2.7 多因子評分：精選5檔 ─────────────────────────────────────────────────
def _v27_score(row):
    score=0.0
    # ① 成長加速 (0-30)
    slope=float(row.get("加速斜率",0) or 0); score+=min(slope*1.5,30)
    # ② 法人連續買超 (0-20)
    consec=int(row.get("連續買超天",0) or 0); score+=min(consec*4,20)
    # ③ 買超比例 (0-10)
    buy_ratio=float(row.get("買超比例",0) or 0)
    if buy_ratio>=70: score+=10
    elif buy_ratio>=60: score+=7
    elif buy_ratio>=50: score+=4
    elif buy_ratio>=40: score+=2
    # ④ PEG (0-20)
    peg=row.get("PEG",None)
    if peg is not None:
        try:
            pg=float(peg)
            if 0<pg<0.3: score+=20
            elif pg<0.5: score+=16
            elif pg<0.8: score+=12
            elif pg<1.0: score+=8
            elif pg<1.5: score+=4
            elif pg<2.0: score+=1
        except: pass
    # ⑤ 超跌折價% (0-20)
    disc=row.get("折價%",None)
    if disc is not None:
        try:
            d=float(disc)
            if d>=30: score+=20
            elif d>=20: score+=15
            elif d>=10: score+=10
            elif d>=5: score+=5
            elif d>=0: score+=2
        except: pass
    # ⑥ ROE (0-15)
    roe=row.get("ROE%",None)
    if roe is not None:
        try:
            rv=float(roe)
            if rv>=25: score+=15
            elif rv>=20: score+=12
            elif rv>=15: score+=8
            elif rv>=10: score+=4
        except: pass
    # ⑦ RSI 超賣加分 (0-10)
    rsi=row.get("RSI",None)
    if rsi is not None:
        try:
            rs=float(rsi)
            if rs<30: score+=10
            elif rs<40: score+=7
            elif rs<50: score+=4
            elif rs<60: score+=1
        except: pass
    # ⑧ 高融資扣分 (-10~+3)
    mr=row.get("融資率%",None)
    if mr is not None:
        try:
            m=float(mr)
            if m>70: score-=10
            elif m>60: score-=5
            elif m<25: score+=3
        except: pass
    return round(score,1)

def recommend_top5(crr):
    """v2.7 多因子評分，精選最多5檔建議進場標的"""
    if crr.empty: return pd.DataFrame()
    df=crr.copy()
    if "毛利率狀態" in df.columns:
        df=df[~df["毛利率狀態"].str.contains("⚠️",na=False)]
    if df.empty: return df
    # Hard filters（有資料才套用）
    if "ROE%" in df.columns: df=df[df["ROE%"].isna()|(df["ROE%"]>=5)]
    if "融資率%" in df.columns: df=df[df["融資率%"].isna()|(df["融資率%"]<=78)]
    if "RSI" in df.columns: df=df[df["RSI"].isna()|(df["RSI"]<=72)]
    if df.empty: return df
    df["v27評分"]=df.apply(_v27_score,axis=1)
    return df.nlargest(5,"v27評分").reset_index(drop=True)

TOP5_ICONS=["🥇","🥈","🥉","4","5"]
TOP5_RANK=["首選","次選","備選","第四","第五"]

def _badge(score):
    s=float(score)
    if s>=75: return "🟢 強力買入","#56d364"
    elif s>=55: return "🟡 建議買入","#f0a500"
    else: return "🔵 值得觀察","#4a9eff"

def render_top5(top5,wl,gh,source="live"):
    """渲染精選5檔精簡表格 + 加入追蹤"""
    if top5.empty: return
    has_enrich="PEG" in top5.columns
    st.markdown("---")
    st.markdown("### 🎯 本月精選 — 最終建議進場清單")
    st.markdown('<div class="alert-gold">系統已從交叉比對結果，綜合成長動能、法人、估值超跌、ROE、RSI、融資率，篩選出以下標的。僅供研究參考，請自行評估風險。</div>',unsafe_allow_html=True)
    st.markdown("")
    wl_ids=[w["stock_id"] for w in wl]

    # ── 精簡表格 ──────────────────────────────────────────────────────────────
    rows_html=""
    for i,(_,row) in enumerate(top5.iterrows()):
        sid=str(row["股票代號"]); nm=row.get("公司名稱","—")
        yoy=float(row.get("最新YoY(%)",0) or 0)
        score=float(row.get("v27評分",row.get("推薦評分",0)) or 0)
        badge,bcolor=_badge(score)
        peg=row.get("PEG",None); disc=row.get("折價%",None)
        rsi=row.get("RSI",None); roe=row.get("ROE%",None); mr=row.get("融資率%",None)
        consec=int(row.get("連續買超天",0) or 0)

        def _fmt_num(v,fmt,fallback="—"):
            if v is None: return fallback
            try: return fmt.format(float(v))
            except: return fallback

        peg_s=_fmt_num(peg,"{:.2f}x")
        disc_s=_fmt_num(disc,"{:+.1f}%")
        disc_c="#56d364" if disc is not None and float(disc)>10 else "#f0a500" if disc is not None and float(disc)>0 else "#ff6b6b" if disc is not None else "#666"
        rsi_s=_fmt_num(rsi,"{:.0f}")
        rsi_c="#56d364" if rsi is not None and float(rsi)<40 else "#f0a500" if rsi is not None and float(rsi)<55 else "#cc8844" if rsi is not None else "#666"
        roe_s=_fmt_num(roe,"{:.1f}%")
        mr_s=_fmt_num(mr,"{:.1f}%")
        mr_c="#ff6b6b" if mr is not None and float(mr)>65 else "#f0a500" if mr is not None and float(mr)>50 else "#aaa"
        bg="#161000" if i==0 else "#0a0f1a"
        rows_html+=(
            '<tr style="background:{bg};border-bottom:1px solid #1e2a3a;">'
            '<td style="padding:12px 8px;font-size:18px;text-align:center;">{icon}</td>'
            '<td style="padding:12px 8px;">'
            '  <div style="font-size:15px;font-weight:bold;color:#f0e070;">{sid}</div>'
            '  <div style="font-size:12px;color:#888;">{nm}</div>'
            '</td>'
            '<td style="padding:12px 8px;"><span style="background:#1a1a00;border:1px solid {bcolor};color:{bcolor};border-radius:4px;padding:2px 7px;font-size:12px;white-space:nowrap;">{badge}</span></td>'
            '<td style="padding:12px 10px;font-size:14px;color:#56d364;font-weight:bold;">{yoy:.1f}%</td>'
            '<td style="padding:12px 10px;font-size:14px;color:#ccc;">{consec}天</td>'
            '<td style="padding:12px 10px;font-size:14px;color:#ccc;">{peg_s}</td>'
            '<td style="padding:12px 10px;font-size:14px;color:{disc_c};font-weight:bold;">{disc_s}</td>'
            '<td style="padding:12px 10px;font-size:14px;color:{rsi_c};">{rsi_s}</td>'
            '<td style="padding:12px 10px;font-size:14px;color:#ccc;">{roe_s}</td>'
            '<td style="padding:12px 10px;font-size:14px;color:{mr_c};">{mr_s}</td>'
            '<td style="padding:12px 10px;font-size:14px;color:{bcolor};font-weight:bold;">{score}</td>'
            '</tr>'
        ).format(
            bg=bg,icon=TOP5_ICONS[i],sid=sid,nm=nm,
            bcolor=bcolor,badge=badge,yoy=yoy,consec=consec,
            peg_s=peg_s,disc_c=disc_c,disc_s=disc_s,
            rsi_c=rsi_c,rsi_s=rsi_s,roe_s=roe_s,
            mr_c=mr_c,mr_s=mr_s,score=score
        )

    table_html=(
        '<div style="overflow-x:auto;margin:4px 0 16px 0;">'
        '<table style="width:100%;border-collapse:collapse;">'
        '<thead><tr style="background:#0d1520;color:#607080;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">'
        '<th style="padding:8px;text-align:center;">#</th>'
        '<th style="padding:8px;text-align:left;">代號</th>'
        '<th style="padding:8px;text-align:left;">評級</th>'
        '<th style="padding:8px;text-align:left;">YoY%</th>'
        '<th style="padding:8px;text-align:left;">法人連買</th>'
        '<th style="padding:8px;text-align:left;">PEG</th>'
        '<th style="padding:8px;text-align:left;">折價</th>'
        '<th style="padding:8px;text-align:left;">RSI</th>'
        '<th style="padding:8px;text-align:left;">ROE</th>'
        '<th style="padding:8px;text-align:left;">融資</th>'
        '<th style="padding:8px;text-align:left;">評分</th>'
        '</tr></thead>'
        '<tbody>{rows}</tbody>'
        '</table></div>'
    ).format(rows=rows_html)

    st.markdown(table_html,unsafe_allow_html=True)

    # 指標說明
    if has_enrich:
        st.markdown(
            '<div style="font-size:11px;color:#506070;margin:0 0 8px 0;">'
            '折價 = 目前PER相對2年歷史中位數的低估幅度（正值＝相對便宜）｜'
            'PEG = 目前PER÷YoY%（越低成長越便宜）｜'
            'RSI &lt; 40 = 超賣區 ｜ 融資 &lt; 50% = 籌碼健康'
            '</div>',unsafe_allow_html=True
        )

    st.markdown("")
    # 加入追蹤按鈕
    btn_cols=st.columns(min(len(top5),5))
    for i,(col,(_,row)) in enumerate(zip(btn_cols,top5.iterrows())):
        sid=str(row["股票代號"]); nm=row.get("公司名稱","—")
        already=sid in wl_ids
        with col:
            btn_lbl="✅ 已追蹤" if already else "📌 {}".format(sid)
            if st.button(btn_lbl,key="add5_{}_{}_{}".format(source,sid,i),disabled=already,width="stretch"):
                yoy=row.get("最新YoY(%)",0); ep=row.get("預估PER",None)
                sc=float(row.get("v27評分",row.get("推薦評分",0)) or 0)
                new_item={"stock_id":sid,"name":nm,"added_date":datetime.today().strftime("%Y-%m-%d"),
                          "added_month":datetime.today().strftime("%Y-%m"),
                          "yoy_at_add":round(float(yoy),1),
                          "est_per_at_add":round(float(ep),1) if ep else None,
                          "score_at_add":sc,"note":"","status":"追蹤中"}
                wl.append(new_item)
                if save_watchlist(wl,gh):
                    st.success("✅ {} {} 已加入追蹤清單！".format(sid,nm)); st.rerun()
                else:
                    st.error("❌ 儲存失敗")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🐋 大戶思維\n#### 投資導航系統 v2.7")
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
    run=st.button("🚀 重新分析",width="stretch",type="primary",disabled=not tok)

st.title("🐋 大戶思維投資導航系統")
st.caption("Module 1 成長動能 × Module 2-1 三大法人 × v2.7 超跌/PEG/ROE/RSI/融資 精選5檔")

t_cross,t_watch,t_m1,t_m2,t_etf,t_hist,t_guide,t_road=st.tabs(["🎯 交叉比對","📌 追蹤清單","📈 Module 1","📊 Module 2","📋 ETF 持股管理","📅 歷史記錄","📖 使用說明","🗺 開發路線圖"])

# ── 追蹤清單 Tab ─────────────────────────────────────────────────────────────
with t_watch:
    st.subheader("📌 追蹤清單")
    if not gh:
        st.markdown('<div class="alert-yellow">⚠️ 需要設定 GitHub Token 才能使用此功能。</div>',unsafe_allow_html=True)
    else:
        wl=load_watchlist(gh)
        if not wl:
            st.markdown('<div class="alert-blue">📭 追蹤清單是空的。<br>在「🎯 交叉比對」Tab 看到精選5檔推薦後，點「📌 加入追蹤清單」即可追蹤。</div>',unsafe_allow_html=True)
        else:
            active=[w for w in wl if w.get("status","")=="追蹤中"]
            closed=[w for w in wl if w.get("status","")!="追蹤中"]
            st.markdown('<div class="alert-green">📊 追蹤中：<strong>{}</strong>　已結束：<strong>{}</strong></div>'.format(len(active),len(closed)),unsafe_allow_html=True)
            st.divider()
            if active:
                st.markdown("### 🔍 目前追蹤中")
                changed=False
                for idx,item in enumerate(wl):
                    if item.get("status","")!="追蹤中": continue
                    sid=item["stock_id"]; nm=item.get("name","—")
                    added=item.get("added_date","—"); mth=item.get("added_month","—")
                    yoy=item.get("yoy_at_add","—"); ep=item.get("est_per_at_add","—")
                    note=item.get("note","")
                    st.markdown(
                        '<div style="background:#0d1520;border-left:4px solid #4a9eff;padding:12px 16px;border-radius:4px;margin:8px 0;">'
                        '<div style="font-size:16px;font-weight:bold;color:#f0e070;">{} {}</div>'
                        '<div style="font-size:13px;color:#888;margin:2px 0;">加入：{}（{}月分析）</div>'
                        '<div style="font-size:13px;color:#ccc;">📈 加入時 YoY：<b>{}%</b>　💰 加入時預估PER：<b>{}</b></div>'
                        '</div>'.format(sid,nm,added,mth,yoy,ep),
                        unsafe_allow_html=True
                    )
                    c1,c2,c3=st.columns([3,1,1])
                    new_note=c1.text_input("備注",value=note,placeholder="例：已買入 10 張 @300，停損設 270...",key="note_{}".format(idx),label_visibility="collapsed")
                    if c2.button("💾 更新備注",key="upd_{}".format(idx),width="stretch"):
                        wl[idx]["note"]=new_note; changed=True; st.toast("✅ {} 備注已更新".format(sid))
                    if c3.button("🏁 標記結束",key="close_{}".format(idx),width="stretch"):
                        wl[idx]["status"]="已結束"; wl[idx]["closed_date"]=datetime.today().strftime("%Y-%m-%d"); changed=True
                        st.toast("🏁 {} 已移至已結束".format(sid))
                    st.markdown("")
                if changed:
                    save_watchlist(wl,gh); st.rerun()
            if closed:
                st.divider(); st.markdown("### 📁 已結束")
                for item in closed:
                    sid=item["stock_id"]; nm=item.get("name","—")
                    added=item.get("added_date","—"); closed_d=item.get("closed_date","—")
                    note=item.get("note","")
                    st.markdown('<div style="background:#111;border-left:4px solid #444;padding:8px 14px;border-radius:4px;margin:4px 0;color:#666;"><b>{} {}</b>　加入：{}　結束：{}　備注：{}</div>'.format(sid,nm,added,closed_d,note or "—"),unsafe_allow_html=True)
            st.divider()
            if st.button("🗑️ 清空全部追蹤清單",key="clear_wl"):
                if save_watchlist([],gh): st.success("✅ 已清空"); st.rerun()
            st.markdown("---")
            st.markdown("""### 📬 自動化追蹤方式
**① 手機書籤法（最簡單）**：把 app URL 加到手機主畫面，每月 10 日後開啟即可

**② Google Calendar 定期提醒**：建立每月 10 日重複提醒：「更新 ETF 持股 + 跑大戶分析」

**③ Streamlit Cloud 月度排程**：每月 10 日設鬧鐘，系統自動存 GitHub，下次直接看""")

# ── ETF 持股管理 Tab ─────────────────────────────────────────────────────────
with t_etf:
    st.subheader("📋 ETF 持股管理")
    st.markdown('<div class="alert-blue">從口袋證券複製持股頁面的全部文字，直接貼上即可。<br>系統自動找出所有股票代號，不需要整理格式。</div>',unsafe_allow_html=True)
    if not gh:
        st.markdown('<div class="alert-yellow">⚠️ 需要設定 GitHub Token 才能使用此功能。</div>',unsafe_allow_html=True)
    else:
        cur=load_etf_holdings(gh)
        c981=cur.get("00981A",[]); c992=cur.get("00992A",[]); upd=cur.get("updated","尚未設定")
        st.markdown('<div class="alert-green">📅 上次更新：<strong>{}</strong>　00981A：<strong>{} 支</strong>　00992A：<strong>{} 支</strong></div>'.format(upd,len(c981),len(c992)),unsafe_allow_html=True)
        st.divider()
        st.markdown("### 📌 00981A 統一台股增長")
        st.markdown("1. 打開 [口袋證券 00981A 持股](https://www.pocket.tw/etf/tw/00981A/fundholding)\n2. 全選所有文字複製\n3. 貼到下方")
        r981=st.text_area("貼上 00981A 持股頁面文字",height=150,placeholder="把複製的全部文字貼這裡，格式不重要...",key="r981")
        if r981.strip():
            p981=parse_stock_ids(r981)
            if p981:
                st.markdown('<div class="alert-green">✅ 自動解析出 <strong>{}</strong> 支股票代號</div>'.format(len(p981)),unsafe_allow_html=True)
                st.code(", ".join(p981))
                new=set(p981)-set(c981); gone=set(c981)-set(p981)
                if new: st.markdown("🆕 **新增：** {}".format(", ".join(sorted(new))))
                if gone: st.markdown("🗑️ **移除：** {}".format(", ".join(sorted(gone))))
            else:
                st.markdown('<div class="alert-yellow">⚠️ 未找到有效股票代號。</div>',unsafe_allow_html=True); p981=c981
        else:
            p981=c981
            if c981: st.markdown("目前清單（{} 支）：`{}{}`".format(len(c981),", ".join(c981[:10]),"..." if len(c981)>10 else ""))
        st.divider()
        st.markdown("### 📌 00992A 群益科技創新")
        st.markdown("1. 打開 [口袋證券 00992A 持股](https://www.pocket.tw/etf/tw/00992A/fundholding)\n2. 全選所有文字複製\n3. 貼到下方")
        r992=st.text_area("貼上 00992A 持股頁面文字",height=150,placeholder="把複製的全部文字貼這裡，格式不重要...",key="r992")
        if r992.strip():
            p992=parse_stock_ids(r992)
            if p992:
                st.markdown('<div class="alert-green">✅ 自動解析出 <strong>{}</strong> 支股票代號</div>'.format(len(p992)),unsafe_allow_html=True)
                st.code(", ".join(p992))
                new=set(p992)-set(c992); gone=set(c992)-set(p992)
                if new: st.markdown("🆕 **新增：** {}".format(", ".join(sorted(new))))
                if gone: st.markdown("🗑️ **移除：** {}".format(", ".join(sorted(gone))))
            else:
                st.markdown('<div class="alert-yellow">⚠️ 未找到有效股票代號。</div>',unsafe_allow_html=True); p992=c992
        else:
            p992=c992
            if c992: st.markdown("目前清單（{} 支）：`{}{}`".format(len(c992),", ".join(c992[:10]),"..." if len(c992)>10 else ""))
        st.divider()
        has_changes=(r981.strip() and p981) or (r992.strip() and p992)
        if st.button("💾 儲存 ETF 持股清單到 GitHub",type="primary",width="stretch",disabled=not has_changes):
            with st.spinner("💾 儲存中..."):
                ok=save_etf_holdings({"00981A":p981,"00992A":p992},gh)
            if ok:
                st.markdown('<div class="alert-green">✅ 儲存成功！00981A：{} 支　00992A：{} 支<br>下次「🚀 重新分析」時會自動整合這份清單。</div>'.format(len(p981),len(p992)),unsafe_allow_html=True)
                st.balloons()
            else:
                st.markdown('<div class="alert-red">❌ 儲存失敗，請確認 GitHub Token 是否正確。</div>',unsafe_allow_html=True)
        if c981 or c992:
            st.divider(); st.markdown("### 📊 下次分析的掃描範圍預覽")
            all_etf=list(dict.fromkeys(c981+c992)); combined=list(dict.fromkeys(WATCHLIST+all_etf))
            etf_only=[s for s in all_etf if s not in WATCHLIST]
            c1,c2,c3=st.columns(3)
            c1.metric("固定清單",f"{len(WATCHLIST)} 支"); c2.metric("ETF 新增",f"{len(etf_only)} 支"); c3.metric("合計掃描",f"{len(combined)} 支")
            if etf_only:
                st.markdown("**ETF 額外補充（不在固定清單內）：**"); st.code(", ".join(etf_only))

with t_guide:
    st.markdown("""
### 📱 每月操作流程（v2.7）
1. 每月 10 日：「📋 ETF 持股管理」更新 00981A / 00992A 持股清單
2. 左側「🚀 重新分析」（約 3-5 分鐘）
3. 「🎯 交叉比對」→ 下拉到「🎯 本月精選」看最終5檔推薦
4. 點「📌 加入追蹤清單」把要追的標的存起來
5. 「📌 追蹤清單」Tab 可加備注（買入價、停損點等）

### 🎯 v2.7 精選5檔評分邏輯
| 因子 | 分值 | 說明 |
|------|------|------|
| 加速斜率 | 0-30分 | 月營收 YoY 加速度 |
| 連續買超天 | 0-20分 | 法人連續進場天數×4 |
| 買超比例 | 0-10分 | 觀察期買超天比例 |
| PEG | 0-20分 | PER÷YoY%，越低越便宜 |
| 超跌折價% | 0-20分 | 目前PER低於2年歷史中位幅度 |
| ROE | 0-15分 | 股東權益報酬率，品質指標 |
| RSI | 0-10分 | 超賣區（<40）加分 |
| 高融資率 | -10分 | 融資>70%扣分（散戶槓桿過高） |

**硬性篩除：** 毛利率異常（⚠️）、ROE < 5%、融資率 > 78%、RSI > 72%

🟢 強力買入（≥75分） ｜ 🟡 建議買入（55-75分） ｜ 🔵 值得觀察（<55分）

### 📊 折價%說明
- **正值（+%）**：目前 PER 低於歷史中位 → 相對便宜
- **負值（−%）**：目前 PER 高於歷史中位 → 相對貴
- 計算方式：(歷史PER中位 − 目前PER) ÷ 歷史PER中位 × 100%
""")

with t_road:
    st.markdown("""
### ✅ 已完成
- Module 1：成長動能篩選 + 做帳偵測
- Module 2-1：三大法人買賣超
- M1 × M2 交叉比對
- GitHub 記憶系統
- v2.5：ETF 持股管理（貼上自動解析）
- v2.6：前3名自動推薦 + 追蹤清單
- **v2.7：超跌/PEG/ROE/RSI/融資率 五層篩選精選5檔** ← 新增

### 🔄 規劃中
- Module 2-2：抗跌強勢偵測
- Module 2-3：發動點偵測（突破盤整第一根）
- Module 3：政策 NLP 分析
- Module 4：停損紀律控制台
""")

# ── 主分析 ────────────────────────────────────────────────────────────────────
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
        st.info("📂 上次分析結果（{}）｜按「🚀 重新分析」更新".format(rt))
        with t_m1:
            st.subheader("📈 Module 1")
            st.markdown('<div class="alert-blue">📂 快取（{}）</div>'.format(rt),unsafe_allow_html=True)
            if not m1r.empty:
                dc=[c for c in ["股票代號","公司名稱","最新YoY(%)","加速斜率","連3月正成長","成長加速中","毛利率狀態"] if c in m1r.columns]
                fmt={k:v for k,v in {"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}"}.items() if k in m1r.columns}
                st.dataframe(m1r[dc].style.map(hl,subset=["毛利率狀態"] if "毛利率狀態" in dc else []).format(fmt),use_container_width=True,height=400)
                st.download_button("📥 下載 M1 CSV",data=m1r[dc].to_csv(index=False,encoding="utf-8-sig"),file_name="m1_{}.csv".format(rt[:7]),mime="text/csv")
        with t_m2:
            st.subheader("📊 Module 2")
            st.markdown('<div class="alert-blue">📂 快取（{}）</div>'.format(rt),unsafe_allow_html=True)
            if not m2r.empty:
                mc=[c for c in ["stock_id","公司名稱","三大合計(張)","外資淨買(張)","投信淨買(張)","連續買超天","買超比例","信號強度"] if c in m2r.columns]
                st.dataframe(m2r[mc].style.map(hl,subset=["信號強度"] if "信號強度" in m2r.columns else []),use_container_width=True,height=400)
        with t_cross:
            st.subheader("🎯 交叉比對")
            st.markdown('<div class="alert-gold"><strong>業績加速成長（M1）＋ 三大法人持續買超（M2）= 雙重確認最強訊號</strong></div>',unsafe_allow_html=True)
            st.markdown('<div class="alert-blue">📂 快取（{}）</div>'.format(rt),unsafe_allow_html=True)
            if crr.empty:
                st.markdown('<div class="alert-yellow">上次無交叉比對結果。</div>',unsafe_allow_html=True)
                if not m1r.empty:
                    dc=[c for c in ["股票代號","公司名稱","最新YoY(%)","加速斜率"] if c in m1r.columns]
                    st.dataframe(m1r[dc],use_container_width=True,height=320)
            else:
                c1,c2,c3,c4=st.columns(4)
                c1.metric("M1 候選",f"{len(m1r)}"); c2.metric("M2 通過",f"{len(m2r)}"); c3.metric("🎯 命中",f"{len(crr)}")
                if "綜合評分" in crr.columns: c4.metric("最高評分","{:.2f}".format(crr["綜合評分"].max()))
                # 精選5檔（快取版：若快取已含新欄位則直接用，否則退回舊評分）
                wl_c=load_watchlist(gh) if gh else []
                top5_c=recommend_top5(crr)
                render_top5(top5_c,wl_c,gh,source="cached")
                st.divider()
                # 完整交叉比對表格（可展開）
                with st.expander("📊 完整交叉比對明細（{} 檔）".format(len(crr)),expanded=False):
                    cc=["股票代號","公司名稱","最新YoY(%)","加速斜率","目前PER","預估PER","PBR",
                        "PEG","折價%","ROE%","RSI","融資率%",
                        "毛利率狀態","三大合計(張)","連續買超天","買超比例","信號強度","綜合評分"]
                    cc=[c for c in cc if c in crr.columns]
                    fmt={k:v for k,v in {"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}","目前PER":"{:.1f}","預估PER":"{:.1f}","PBR":"{:.1f}","PEG":"{:.2f}","折價%":"{:.1f}%","ROE%":"{:.1f}%","RSI":"{:.1f}","融資率%":"{:.1f}%","三大合計(張)":"{:.0f}","買超比例":"{:.1f}%","綜合評分":"{:.2f}"}.items() if k in crr.columns}
                    st.dataframe(crr[cc].style.map(hl,subset=[c for c in ["信號強度","毛利率狀態"] if c in cc]).format(fmt).background_gradient(subset=["綜合評分"],cmap="YlOrRd"),use_container_width=True,height=420)
                    st.download_button("📥 下載交叉比對 CSV",data=crr[cc].to_csv(index=False,encoding="utf-8-sig"),file_name="cross_{}.csv".format(rt[:7]),mime="text/csv")

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
            if added>0: st.info("✅ 已整合 ETF 持股：00981A（{}支）+ 00992A（{}支），新增 {} 支，合計掃描 {} 支".format(len(e981),len(e992),added,len(scan)))
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
            st.success("✅ 成功取得 {} 支股票營收資料".format(scanned))
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
                st.download_button("📥 下載 M1 CSV",data=m1r[dc].to_csv(index=False,encoding="utf-8-sig"),file_name="m1_{}.csv".format(datetime.today().strftime("%Y%m%d")),mime="text/csv")

        with t_m2:
            st.subheader("📊 Module 2-1 — 三大法人買賣超")
            m1c=len(m1r) if "m1r" in dir() else 0
            st.markdown('<div class="alert-green">✅ 只針對 M1 篩出的 <strong>{} 支候選</strong>做法人追蹤</div>'.format(m1c),unsafe_allow_html=True)
            if "m1r" not in dir() or m1r.empty: st.warning("請先完成 Module 1。"); m2r=pd.DataFrame()
            else:
                m2r=inst_scan(m1r,m2s,tok,mc,mr)
                if m2r.empty: st.markdown('<div class="alert-yellow">M1 候選中目前無股票符合法人買超條件。</div>',unsafe_allow_html=True)
                else:
                    c1,c2,c3=st.columns(3)
                    strong=len(m2r[m2r["信號強度"].str.contains("🔥")]); steady=len(m2r[m2r["信號強度"].str.contains("✅")])
                    c1.metric("通過 M2",f"{len(m2r)}"); c2.metric("🔥 強力",f"{strong}"); c3.metric("✅ 持續",f"{steady}")
                    m2c=[c for c in ["stock_id","公司名稱","三大合計(張)","外資淨買(張)","投信淨買(張)","自營淨買(張)","連續買超天","買超比例","信號強度"] if c in m2r.columns]
                    st.dataframe(m2r[m2c].style.map(hl,subset=["信號強度"]).format({"買超比例":"{:.1f}%","三大合計(張)":"{:.0f}","外資淨買(張)":"{:.0f}","投信淨買(張)":"{:.0f}","自營淨買(張)":"{:.0f}"}).background_gradient(subset=["連續買超天"],cmap="YlGn"),use_container_width=True,height=400)
                    st.download_button("📥 下載 M2 CSV",data=m2r[m2c].to_csv(index=False,encoding="utf-8-sig"),file_name="m2_{}.csv".format(datetime.today().strftime("%Y%m%d")),mime="text/csv")

        with t_cross:
            st.subheader("🎯 交叉比對 — M1 × M2 最強訊號")
            st.markdown('<div class="alert-gold"><strong>業績加速成長（M1）＋ 三大法人持續買超（M2）= 雙重確認最強訊號</strong></div>',unsafe_allow_html=True)
            crr=pd.DataFrame()
            m1ok="m1r" in dir() and not m1r.empty; m2ok="m2r" in dir() and not m2r.empty
            if m1ok and m2ok: crr=cross(m1r,m2r,tok)
            if not m1ok: st.info("請先執行分析。")
            elif not m2ok or crr.empty:
                st.markdown('<div class="alert-yellow">目前無股票同時通過 M1 和 M2。M1 候選名單供參考：</div>',unsafe_allow_html=True)
                if m1ok:
                    dc=[c for c in ["股票代號","公司名稱","最新YoY(%)","加速斜率","毛利率狀態"] if c in m1r.columns]
                    st.dataframe(m1r[dc],use_container_width=True,height=320)
            else:
                c1,c2,c3,c4=st.columns(4)
                c1.metric("M1 候選",f"{len(m1r)}"); c2.metric("M2 通過",f"{len(m2r)}"); c3.metric("🎯 命中",f"{len(crr)}")
                if "綜合評分" in crr.columns: c4.metric("最高評分","{:.2f}".format(crr["綜合評分"].max()))

                # ── v2.7 深度估值層 ──────────────────────────────────────────
                crr=enrich_cross(crr,tok)

                # ── 精選5檔（主角）──────────────────────────────────────────
                wl_live=load_watchlist(gh) if gh else []
                top5_live=recommend_top5(crr)
                render_top5(top5_live,wl_live,gh,source="live")

                st.divider()
                # ── 完整交叉比對明細（收合）──────────────────────────────────
                with st.expander("📊 完整交叉比對明細（{} 檔）".format(len(crr)),expanded=False):
                    if "目前PER" in crr.columns:
                        st.markdown('<div class="alert-blue">📊 <strong>指標說明：</strong>折價% = (歷史PER中位-目前PER)/歷史PER中位×100 ｜ PEG = 目前PER÷YoY% ｜ RSI-14</div>',unsafe_allow_html=True)
                    cc=["股票代號","公司名稱","最新YoY(%)","加速斜率","目前PER","預估PER","PBR",
                        "PEG","歷史PER中位","折價%","ROE%","RSI","融資率%",
                        "毛利率狀態","三大合計(張)","連續買超天","買超比例","信號強度","綜合評分","v27評分"]
                    cc=[c for c in cc if c in crr.columns]
                    fmt={k:v for k,v in {"最新YoY(%)":"{:.1f}%","加速斜率":"{:.2f}","目前PER":"{:.1f}","預估PER":"{:.1f}","PBR":"{:.1f}","歷史PER中位":"{:.1f}","PEG":"{:.2f}","折價%":"{:+.1f}%","ROE%":"{:.1f}%","RSI":"{:.1f}","融資率%":"{:.1f}%","三大合計(張)":"{:.0f}","買超比例":"{:.1f}%","綜合評分":"{:.2f}","v27評分":"{:.1f}"}.items() if k in crr.columns}
                    st.dataframe(crr[cc].style.map(hl,subset=[c for c in ["信號強度","毛利率狀態"] if c in cc]).format(fmt).background_gradient(subset=["v27評分"] if "v27評分" in crr.columns else ["綜合評分"],cmap="YlOrRd"),use_container_width=True,height=420)
                    st.download_button("📥 下載完整分析 CSV",data=crr[cc].to_csv(index=False,encoding="utf-8-sig"),file_name="cross_{}.csv".format(datetime.today().strftime("%Y%m%d")),mime="text/csv")

        if gh and "m1r" in dir():
            params={"months_back":mb,"min_yoy":my,"min_slope":ms,"margin_threshold":mt,"min_consec":mc,"min_buy_ratio":mr}
            m2sv=m2r if "m2r" in dir() else pd.DataFrame(); crsv=crr if "crr" in dir() else pd.DataFrame()
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
                    d=json.loads(c); st.markdown("**分析時間：** {}".format(d.get("run_time","—")))
                    hc=pd.DataFrame(d.get("cross_result",[]))
                    if not hc.empty:
                        sc=[c for c in ["股票代號","公司名稱","最新YoY(%)","加速斜率","連續買超天","信號強度","綜合評分","v27評分","折價%","RSI"] if c in hc.columns]
                        st.dataframe(hc[sc],use_container_width=True,height=300)
