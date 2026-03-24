"""
台股 ETF 歷史資料回補腳本（純 requests 版，不需要 supabase 套件）
撈取過去 6 個月的資料，寫入 Supabase
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta

# ─── 環境變數 ───
FINMIND_TOKEN = os.environ.get("FINMIND_API_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not all([FINMIND_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    print("=" * 50)
    print("缺少環境變數！請先設定：")
    print("")
    print('$env:FINMIND_API_TOKEN="你的token"')
    print('$env:SUPABASE_URL="https://xxx.supabase.co"')
    print('$env:SUPABASE_SERVICE_ROLE_KEY="你的key"')
    print("=" * 50)
    sys.exit(1)

# ─── 設定 ───
FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
SUPABASE_REST = f"{SUPABASE_URL}/rest/v1"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

TODAY = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
DELAY = 3


# ─── 通用函式 ───

def fetch_finmind(dataset, params=None):
    if params is None:
        params = {}
    params["dataset"] = dataset
    headers = {"Authorization": f"Bearer {FINMIND_TOKEN}"}
    try:
        resp = requests.get(FINMIND_BASE, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("msg") != "success":
            print(f"  ⚠ FinMind: {data.get('msg', '未知')}")
            return []
        return data.get("data", [])
    except Exception as e:
        print(f"  ❌ FinMind 請求失敗: {e}")
        return []


def upsert_supabase(table, rows):
    """用 POST + Prefer: resolution=merge-duplicates 寫入 Supabase"""
    if not rows:
        return 0
    try:
        # 分批寫入，每批 50 筆
        total = 0
        for i in range(0, len(rows), 50):
            batch = rows[i:i+50]
            resp = requests.post(
                f"{SUPABASE_REST}/{table}",
                headers=SUPABASE_HEADERS,
                json=batch,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                total += len(batch)
            else:
                print(f"  ⚠ Supabase 寫入失敗: {resp.status_code} {resp.text[:200]}")
        return total
    except Exception as e:
        print(f"  ❌ Supabase 寫入錯誤: {e}")
        return 0


def get_etf_ids():
    try:
        resp = requests.get(
            f"{SUPABASE_REST}/etf_info?select=id",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            timeout=15,
        )
        return [row["id"] for row in resp.json()] if resp.status_code == 200 else []
    except Exception as e:
        print(f"❌ 無法讀取 ETF 清單: {e}")
        return []


# ─── 回補各類資料 ───

def backfill_prices(etf_ids):
    print("\n" + "=" * 50)
    print("📊 回補股價（6 個月）...")
    print("=" * 50)
    total = 0

    for i, etf_id in enumerate(etf_ids):
        print(f"  [{i+1}/{len(etf_ids)}] {etf_id}...", end=" ")
        data = fetch_finmind("TaiwanStockPrice", {
            "data_id": etf_id,
            "start_date": START_DATE,
        })
        if not data:
            print("無資料")
            time.sleep(DELAY)
            continue

        rows = [{
            "etf_id": etf_id,
            "date": d["date"],
            "open": d.get("open"),
            "high": d.get("max"),
            "low": d.get("min"),
            "close": d.get("close"),
            "volume": d.get("Trading_Volume"),
            "spread": d.get("spread"),
        } for d in data]

        count = upsert_supabase("etf_daily_price", rows)
        total += count
        print(f"✅ {count} 筆")
        time.sleep(DELAY)

    return total


def backfill_valuations(etf_ids):
    print("\n" + "=" * 50)
    print("📈 回補估值（PER / PBR / 殖利率）...")
    print("=" * 50)
    total = 0

    for i, etf_id in enumerate(etf_ids):
        print(f"  [{i+1}/{len(etf_ids)}] {etf_id}...", end=" ")
        data = fetch_finmind("TaiwanStockPER", {
            "data_id": etf_id,
            "start_date": START_DATE,
        })
        if not data:
            print("無資料")
            time.sleep(DELAY)
            continue

        rows = [{
            "etf_id": etf_id,
            "date": d["date"],
            "dividend_yield": d.get("dividend_yield"),
            "per": d.get("PER"),
            "pbr": d.get("PBR"),
        } for d in data]

        count = upsert_supabase("etf_valuation", rows)
        total += count
        print(f"✅ {count} 筆")
        time.sleep(DELAY)

    return total


def backfill_institutional(etf_ids):
    print("\n" + "=" * 50)
    print("🏛️ 回補三大法人買賣超...")
    print("=" * 50)
    total = 0

    for i, etf_id in enumerate(etf_ids):
        print(f"  [{i+1}/{len(etf_ids)}] {etf_id}...", end=" ")
        data = fetch_finmind("TaiwanStockInstitutionalInvestorsBuySell", {
            "data_id": etf_id,
            "start_date": START_DATE,
        })
        if not data:
            print("無資料")
            time.sleep(DELAY)
            continue

        rows = [{
            "etf_id": etf_id,
            "date": d["date"],
            "investor_type": d.get("name", ""),
            "buy": d.get("buy", 0),
            "sell": d.get("sell", 0),
        } for d in data]

        count = upsert_supabase("etf_institutional", rows)
        total += count
        print(f"✅ {count} 筆")
        time.sleep(DELAY)

    return total


def backfill_dividends(etf_ids):
    print("\n" + "=" * 50)
    print("💰 回補配息紀錄...")
    print("=" * 50)
    total = 0

    for i, etf_id in enumerate(etf_ids):
        print(f"  [{i+1}/{len(etf_ids)}] {etf_id}...", end=" ")
        data = fetch_finmind("TaiwanStockDividend", {
            "data_id": etf_id,
            "start_date": "2020-01-01",
        })
        if not data:
            print("無資料")
            time.sleep(DELAY)
            continue

        rows = []
        for d in data:
            ex_date = d.get("date")
            if not ex_date:
                continue
            rows.append({
                "etf_id": etf_id,
                "ex_date": ex_date,
                "cash_dividend": d.get("CashEarningsDistribution", 0),
                "stock_dividend": d.get("StockEarningsDistribution", 0),
                "year": d.get("year", ""),
            })

        count = upsert_supabase("etf_dividend", rows)
        total += count
        print(f"✅ {count} 筆")
        time.sleep(DELAY)

    return total


# ─── 主程式 ───
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ETF 歷史資料回補（純 requests 版）")
    print(f"📅 回補範圍: {START_DATE} ~ {TODAY}")
    print(f"⏱️ 每次請求間隔 {DELAY} 秒")
    print("=" * 60)

    etf_ids = get_etf_ids()
    print(f"\n📋 共 {len(etf_ids)} 檔 ETF: {', '.join(etf_ids)}")

    if not etf_ids:
        print("❌ etf_info 表是空的！")
        sys.exit(1)

    total_requests = len(etf_ids) * 4
    est_minutes = (total_requests * DELAY) / 60
    print(f"⏱️ 預估約 {est_minutes:.0f} 分鐘")
    print("\n開始回補...\n")

    p = backfill_prices(etf_ids)
    v = backfill_valuations(etf_ids)
    i = backfill_institutional(etf_ids)
    d = backfill_dividends(etf_ids)

    print("\n" + "=" * 60)
    print("✅ 歷史回補完成！")
    print(f"   股價:   {p} 筆")
    print(f"   估值:   {v} 筆")
    print(f"   法人:   {i} 筆")
    print(f"   配息:   {d} 筆")
    print("=" * 60)
    print("\n🎉 重新整理儀表板，所有分頁都應該有資料了！")
