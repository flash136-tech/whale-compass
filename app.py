# 大戶思維投資導航系統 v2.6 - 前3名推薦 + 追蹤清單
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
