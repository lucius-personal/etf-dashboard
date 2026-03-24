"""
回補 3 年股價歷史資料（用於計算年化報酬率）
只補股價，法人和配息不需要 3 年
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
    print("缺少環境變數！"); sys.exit(1)

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
REST = f"{SUPABASE_URL}/rest/v1"
DELAY = 3

TODAY = datetime.now().strftime("%Y-%m-%d")
# 3 年前
START_3Y = (datetime.now() - timedelta(days=1095)).strftime("%Y-%m-%d")
# 6 個月前（已經有的資料起點，避免重複撈太多）
START_6M = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")


def supa_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def fetch_finmind(dataset, params):
    params["dataset"] = dataset
    headers = {"Authorization": f"Bearer {FINMIND_TOKEN}"}
    try:
        resp = requests.get(FINMIND_BASE, params=params, headers=headers, timeout=60)
        data = resp.json()
        if data.get("msg") != "success":
            return []
        return data.get("data", [])
    except Exception as e:
        print(f"  ❌ {e}")
        return []


def upsert(table, rows, conflict):
    if not rows:
        return 0
    total = 0
    url = f"{REST}/{table}?on_conflict={conflict}"
    for i in range(0, len(rows), 50):
        batch = rows[i:i+50]
        try:
            resp = requests.post(url, headers=supa_headers(), json=batch, timeout=30)
            if resp.status_code in (200, 201):
                total += len(batch)
        except:
            pass
    return total


def get_etf_ids():
    resp = requests.get(f"{REST}/etf_info?select=id",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    return [r["id"] for r in resp.json()] if resp.status_code == 200 else []


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 回補 3 年股價歷史（用於年化報酬率計算）")
    print(f"📅 範圍: {START_3Y} ~ {START_6M}")
    print("   （6 個月內的資料之前已經補過了）")
    print("=" * 60)

    etf_ids = get_etf_ids()
    print(f"\n📋 共 {len(etf_ids)} 檔 ETF")

    # FinMind 免費版一次最多回傳約 1000 筆
    # 3 年大約 750 個交易日，一次撈得完
    # 但為了避免限流，分兩段撈：3年前~1.5年前, 1.5年前~6個月前

    MID = (datetime.now() - timedelta(days=547)).strftime("%Y-%m-%d")

    total = 0
    for i, eid in enumerate(etf_ids):
        print(f"\n  [{i+1}/{len(etf_ids)}] {eid}")

        # 前半段：3年前 ~ 1.5年前
        print(f"    前半 ({START_3Y} ~ {MID})...", end=" ")
        data1 = fetch_finmind("TaiwanStockPrice", {
            "data_id": eid, "start_date": START_3Y, "end_date": MID,
        })
        rows1 = [{"etf_id": eid, "date": d["date"], "open": d.get("open"),
                  "high": d.get("max"), "low": d.get("min"), "close": d.get("close"),
                  "volume": d.get("Trading_Volume"), "spread": d.get("spread")}
                 for d in data1] if data1 else []
        c1 = upsert("etf_daily_price", rows1, "etf_id,date")
        print(f"✅ {c1} 筆")
        time.sleep(DELAY)

        # 後半段：1.5年前 ~ 6個月前
        print(f"    後半 ({MID} ~ {START_6M})...", end=" ")
        data2 = fetch_finmind("TaiwanStockPrice", {
            "data_id": eid, "start_date": MID, "end_date": START_6M,
        })
        rows2 = [{"etf_id": eid, "date": d["date"], "open": d.get("open"),
                  "high": d.get("max"), "low": d.get("min"), "close": d.get("close"),
                  "volume": d.get("Trading_Volume"), "spread": d.get("spread")}
                 for d in data2] if data2 else []
        c2 = upsert("etf_daily_price", rows2, "etf_id,date")
        print(f"✅ {c2} 筆")
        time.sleep(DELAY)

        total += c1 + c2

    print(f"\n{'=' * 60}")
    print(f"✅ 3 年股價回補完成！共 {total} 筆")
    print(f"{'=' * 60}")
