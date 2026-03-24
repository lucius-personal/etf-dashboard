"""
診斷 + 修復腳本
1. 檢查 Supabase 裡 investor_type 的實際值
2. 從配息紀錄 + 股價計算殖利率，寫入 etf_valuation
"""

import os
import sys
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("缺少環境變數！")
    sys.exit(1)

REST = f"{SUPABASE_URL}/rest/v1"
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
HW = {**H, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}


def get(table, params=""):
    r = requests.get(f"{REST}/{table}?{params}", headers=H, timeout=15)
    return r.json() if r.status_code == 200 else []


# ════════════════════════════════════
# 1. 診斷 investor_type
# ════════════════════════════════════
print("=" * 60)
print("🔍 診斷 investor_type 值")
print("=" * 60)

# 撈一小筆法人資料看 investor_type 的值
inst_sample = get("etf_institutional", "select=investor_type&limit=50")
types = set(d["investor_type"] for d in inst_sample)
print(f"\n法人資料中的 investor_type 值:")
for t in sorted(types):
    print(f"  → '{t}'")

# ════════════════════════════════════
# 2. 檢查各表筆數
# ════════════════════════════════════
print(f"\n{'=' * 60}")
print("📊 各表資料筆數")
print("=" * 60)

for table in ["etf_daily_price", "etf_valuation", "etf_institutional", "etf_dividend"]:
    data = get(table, "select=id&limit=1&order=id.desc")
    # 用 head request 拿 count
    r = requests.get(
        f"{REST}/{table}?select=id",
        headers={**H, "Prefer": "count=exact"},
        timeout=15,
    )
    count = r.headers.get("content-range", "unknown")
    print(f"  {table}: {count}")

# ════════════════════════════════════
# 3. 計算殖利率並寫入
# ════════════════════════════════════
print(f"\n{'=' * 60}")
print("📈 計算殖利率（從配息紀錄 + 最新股價）")
print("=" * 60)

# 取得所有 ETF
etfs = get("etf_info", "select=id,name,is_distributing")

# 取得每檔的最新股價
# 取得每檔的近一年配息總額
from datetime import datetime, timedelta
one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
today = datetime.now().strftime("%Y-%m-%d")

valuation_rows = []

for etf in etfs:
    eid = etf["id"]
    name = etf.get("name", "")
    is_dist = etf.get("is_distributing", True)

    # 最新收盤價
    prices = get("etf_daily_price", f"select=close,date&etf_id=eq.{eid}&order=date.desc&limit=1")
    if not prices:
        print(f"  {eid} {name}: 無股價資料")
        continue
    latest_price = prices[0]["close"]
    latest_date = prices[0]["date"]

    if not is_dist:
        # 不配息的 ETF
        valuation_rows.append({
            "etf_id": eid,
            "date": latest_date,
            "dividend_yield": 0,
            "per": None,
            "pbr": None,
        })
        print(f"  {eid} {name}: 不配息 (price=${latest_price})")
        continue

    # 近一年配息總額
    divs = get("etf_dividend", f"select=cash_dividend&etf_id=eq.{eid}&ex_date=gte.{one_year_ago}")
    total_div = sum(d.get("cash_dividend", 0) or 0 for d in divs)

    if total_div > 0 and latest_price > 0:
        yld = round(total_div / latest_price * 100, 2)
    else:
        yld = None

    valuation_rows.append({
        "etf_id": eid,
        "date": latest_date,
        "dividend_yield": yld,
        "per": None,
        "pbr": None,
    })
    print(f"  {eid} {name}: 近一年配息 ${total_div:.2f} / 股價 ${latest_price} = 殖利率 {yld}%")

# 寫入 Supabase
if valuation_rows:
    url = f"{REST}/etf_valuation?on_conflict=etf_id,date"
    r = requests.post(url, headers=HW, json=valuation_rows, timeout=30)
    if r.status_code in (200, 201):
        print(f"\n  ✅ 已寫入 {len(valuation_rows)} 筆估值資料")
    else:
        print(f"\n  ❌ 寫入失敗: {r.status_code} {r.text[:200]}")

# ════════════════════════════════════
# 4. 告訴使用者前端要怎麼修
# ════════════════════════════════════
print(f"\n{'=' * 60}")
print("🔧 前端修正建議")
print("=" * 60)

print(f"""
法人資料的 investor_type 值是: {sorted(types)}

你的前端 Dashboard.js 裡面比對法人類型的邏輯需要用這些值。
請把下面的對照表記下來，我會幫你更新前端：
""")

# 常見的 FinMind investor_type 對照
mapping = {
    "Foreign_Investor": "外資",
    "Investment_Trust": "投信",
    "Dealer_self": "自營商(自行)",
    "Dealer_Hedging": "自營商(避險)",
    "Dealer_total": "自營商(合計)",
    "Foreign_Dealer_Self": "外資(自行)",
    "Foreign_Dealer_Hedging": "外資(避險)",
}

for eng, chi in mapping.items():
    if eng in types:
        print(f"  '{eng}' → {chi}")

print(f"\n{'=' * 60}")
print("✅ 診斷完成！")
print("=" * 60)
