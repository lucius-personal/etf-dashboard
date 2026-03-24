"""
台股 ETF 歷史資料回補腳本（跑一次就好）
撈取過去 6 個月的資料，寫入 Supabase
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta
from supabase import create_client

# ─── 環境變數 ───
FINMIND_TOKEN = os.environ.get("FINMIND_API_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not all([FINMIND_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    print("=" * 50)
    print("缺少環境變數！請用以下方式執行：")
    print("")
    print('$env:FINMIND_API_TOKEN="你的token"')
    print('$env:SUPABASE_URL="https://xxx.supabase.co"')
    print('$env:SUPABASE_SERVICE_ROLE_KEY="你的key"')
    print("python scripts/backfill.py")
    print("=" * 50)
    sys.exit(1)

# ─── 初始化 ───
FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 回補 6 個月
TODAY = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

# FinMind 免費版限制 600 req/hr，每次請求間隔 3 秒避免撞限制
DELAY = 3


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
            print(f"  ⚠ FinMind: {data.get('msg', '未知錯誤')}")
            return []

        return data.get("data", [])
    except Exception as e:
        print(f"  ❌ 請求失敗: {e}")
        return []


def get_etf_ids():
    result = supabase.table("etf_info").select("id").execute()
    return [row["id"] for row in result.data] if result.data else []


def backfill_prices(etf_ids):
    print("\n" + "=" * 50)
    print("📊 回補股價（6 個月）...")
    print("=" * 50)
    total = 0

    for i, etf_id in enumerate(etf_ids):
        print(f"\n  [{i+1}/{len(etf_ids)}] {etf_id}...", end=" ")
        data = fetch_finmind("TaiwanStockPrice", {
            "data_id": etf_id,
            "start_date": START_DATE,
        })

        if not data:
            print("無資料")
            time.sleep(DELAY)
            continue

        rows = []
        for d in data:
            rows.append({
                "etf_id": etf_id,
                "date": d["date"],
                "open": d.get("open"),
                "high": d.get("max"),
                "low": d.get("min"),
                "close": d.get("close"),
                "volume": d.get("Trading_Volume"),
                "spread": d.get("spread"),
            })

        if rows:
            try:
                # 分批寫入，每批 50 筆
                for j in range(0, len(rows), 50):
                    batch = rows[j:j+50]
                    supabase.table("etf_daily_price").upsert(
                        batch, on_conflict="etf_id,date"
                    ).execute()
                total += len(rows)
                print(f"✅ {len(rows)} 筆")
            except Exception as e:
                print(f"❌ {e}")

        time.sleep(DELAY)

    return total


def backfill_valuations(etf_ids):
    print("\n" + "=" * 50)
    print("📈 回補估值指標（PER / PBR / 殖利率）...")
    print("=" * 50)
    total = 0

    for i, etf_id in enumerate(etf_ids):
        print(f"\n  [{i+1}/{len(etf_ids)}] {etf_id}...", end=" ")
        data = fetch_finmind("TaiwanStockPER", {
            "data_id": etf_id,
            "start_date": START_DATE,
        })

        if not data:
            print("無資料")
            time.sleep(DELAY)
            continue

        rows = []
        for d in data:
            rows.append({
                "etf_id": etf_id,
                "date": d["date"],
                "dividend_yield": d.get("dividend_yield"),
                "per": d.get("PER"),
                "pbr": d.get("PBR"),
            })

        if rows:
            try:
                for j in range(0, len(rows), 50):
                    batch = rows[j:j+50]
                    supabase.table("etf_valuation").upsert(
                        batch, on_conflict="etf_id,date"
                    ).execute()
                total += len(rows)
                print(f"✅ {len(rows)} 筆")
            except Exception as e:
                print(f"❌ {e}")

        time.sleep(DELAY)

    return total


def backfill_institutional(etf_ids):
    print("\n" + "=" * 50)
    print("🏛️ 回補三大法人買賣超...")
    print("=" * 50)
    total = 0

    for i, etf_id in enumerate(etf_ids):
        print(f"\n  [{i+1}/{len(etf_ids)}] {etf_id}...", end=" ")
        data = fetch_finmind("TaiwanStockInstitutionalInvestorsBuySell", {
            "data_id": etf_id,
            "start_date": START_DATE,
        })

        if not data:
            print("無資料")
            time.sleep(DELAY)
            continue

        rows = []
        for d in data:
            rows.append({
                "etf_id": etf_id,
                "date": d["date"],
                "investor_type": d.get("name", ""),
                "buy": d.get("buy", 0),
                "sell": d.get("sell", 0),
            })

        if rows:
            try:
                for j in range(0, len(rows), 50):
                    batch = rows[j:j+50]
                    supabase.table("etf_institutional").upsert(
                        batch, on_conflict="etf_id,date,investor_type"
                    ).execute()
                total += len(rows)
                print(f"✅ {len(rows)} 筆")
            except Exception as e:
                print(f"❌ {e}")

        time.sleep(DELAY)

    return total


def backfill_dividends(etf_ids):
    print("\n" + "=" * 50)
    print("💰 回補配息紀錄（從 2020 年起）...")
    print("=" * 50)
    total = 0

    for i, etf_id in enumerate(etf_ids):
        print(f"\n  [{i+1}/{len(etf_ids)}] {etf_id}...", end=" ")
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

        if rows:
            try:
                supabase.table("etf_dividend").upsert(
                    rows, on_conflict="etf_id,ex_date"
                ).execute()
                total += len(rows)
                print(f"✅ {len(rows)} 筆")
            except Exception as e:
                print(f"❌ {e}")

        time.sleep(DELAY)

    return total


# ─── 主程式 ───
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ETF 歷史資料回補")
    print(f"📅 回補範圍: {START_DATE} ~ {TODAY}（約 6 個月）")
    print(f"⏱️ 每次請求間隔 {DELAY} 秒，避免 FinMind 限流")
    print("=" * 60)

    etf_ids = get_etf_ids()
    print(f"\n📋 共 {len(etf_ids)} 檔 ETF: {', '.join(etf_ids)}")

    if not etf_ids:
        print("❌ etf_info 表是空的！")
        sys.exit(1)

    # 預估時間
    total_requests = len(etf_ids) * 4  # 4 種資料
    est_minutes = (total_requests * DELAY) / 60
    print(f"⏱️ 預估需要 {est_minutes:.0f} 分鐘（{total_requests} 個請求 × {DELAY} 秒間隔）")
    print("\n開始回補...\n")

    price_count = backfill_prices(etf_ids)
    val_count = backfill_valuations(etf_ids)
    inst_count = backfill_institutional(etf_ids)
    div_count = backfill_dividends(etf_ids)

    print("\n" + "=" * 60)
    print("✅ 歷史回補完成！")
    print(f"   股價:   {price_count} 筆")
    print(f"   估值:   {val_count} 筆")
    print(f"   法人:   {inst_count} 筆")
    print(f"   配息:   {div_count} 筆")
    print("=" * 60)
    print("\n🎉 現在重新打開儀表板，所有分頁都應該有資料了！")
