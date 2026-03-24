"""
台股 ETF 每日資料同步腳本（純 requests 版）
每天由 GitHub Actions 在盤後自動執行
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta

FINMIND_TOKEN = os.environ.get("FINMIND_API_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not all([FINMIND_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    print("❌ 缺少環境變數！"); sys.exit(1)

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
REST = f"{SUPABASE_URL}/rest/v1"
TODAY = datetime.now().strftime("%Y-%m-%d")
START = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
ONE_YEAR_AGO = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
DELAY = 3


def supa_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def supa_read():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def fetch_fm(dataset, params):
    params["dataset"] = dataset
    headers = {"Authorization": f"Bearer {FINMIND_TOKEN}"}
    try:
        r = requests.get(FINMIND_BASE, params=params, headers=headers, timeout=30)
        d = r.json()
        return d.get("data", []) if d.get("msg") == "success" else []
    except Exception as e:
        print(f"  ❌ {e}"); return []


def upsert(table, rows, conflict):
    if not rows: return 0
    total = 0
    url = f"{REST}/{table}?on_conflict={conflict}"
    for i in range(0, len(rows), 50):
        batch = rows[i:i+50]
        try:
            r = requests.post(url, headers=supa_headers(), json=batch, timeout=30)
            if r.status_code in (200, 201): total += len(batch)
        except: pass
    return total


def get_etf_ids():
    r = requests.get(f"{REST}/etf_info?select=id,is_distributing", headers=supa_read())
    return r.json() if r.status_code == 200 else []


print("=" * 50)
print(f"🚀 ETF 每日同步 {TODAY}")
print("=" * 50)

etfs = get_etf_ids()
etf_ids = [e["id"] for e in etfs]
print(f"📋 {len(etf_ids)} 檔 ETF\n")

# ─── 1. 股價 ───
print("📊 同步股價...")
pt = 0
for eid in etf_ids:
    d = fetch_fm("TaiwanStockPrice", {"data_id": eid, "start_date": START})
    if d:
        rows = [{"etf_id": eid, "date": x["date"], "open": x.get("open"), "high": x.get("max"),
                 "low": x.get("min"), "close": x.get("close"), "volume": x.get("Trading_Volume"),
                 "spread": x.get("spread")} for x in d]
        pt += upsert("etf_daily_price", rows, "etf_id,date")
    time.sleep(DELAY)
print(f"  ✅ {pt} 筆\n")

# ─── 2. 法人 ───
print("🏛️ 同步法人...")
it = 0
for eid in etf_ids:
    d = fetch_fm("TaiwanStockInstitutionalInvestorsBuySell", {"data_id": eid, "start_date": START})
    if d:
        rows = [{"etf_id": eid, "date": x["date"], "investor_type": x.get("name", ""),
                 "buy": x.get("buy", 0), "sell": x.get("sell", 0)} for x in d]
        it += upsert("etf_institutional", rows, "etf_id,date,investor_type")
    time.sleep(DELAY)
print(f"  ✅ {it} 筆\n")

# ─── 3. 計算殖利率（從配息 + 股價）───
print("📈 計算殖利率...")
vt = 0
for e in etfs:
    eid = e["id"]
    is_dist = e.get("is_distributing", True)

    # 最新股價
    pr = requests.get(f"{REST}/etf_daily_price?select=close,date&etf_id=eq.{eid}&order=date.desc&limit=1", headers=supa_read())
    prices = pr.json() if pr.status_code == 200 else []
    if not prices: continue
    price = prices[0]["close"]
    date = prices[0]["date"]

    if not is_dist:
        yld = 0
    else:
        dr = requests.get(f"{REST}/etf_dividend?select=cash_dividend&etf_id=eq.{eid}&ex_date=gte.{ONE_YEAR_AGO}", headers=supa_read())
        divs = dr.json() if dr.status_code == 200 else []
        total_div = sum(d.get("cash_dividend", 0) or 0 for d in divs)
        yld = round(total_div / price * 100, 2) if price > 0 and total_div > 0 else None

    row = {"etf_id": eid, "date": date, "dividend_yield": yld, "per": None, "pbr": None}
    vt += upsert("etf_valuation", [row], "etf_id,date")
print(f"  ✅ {vt} 筆\n")

# ─── 結果 ───
print("=" * 50)
print(f"✅ 同步完成！股價:{pt} 法人:{it} 估值:{vt}")
print("=" * 50)
