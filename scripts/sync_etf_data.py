"""
台股 ETF 資料同步腳本
每天由 GitHub Actions 在盤後（14:30 TST）自動執行
從 FinMind API 撈資料 → 寫入 Supabase
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from supabase import create_client

# ─── 環境變數 ───
FINMIND_TOKEN = os.environ.get("FINMIND_API_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not all([FINMIND_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    print("❌ 缺少環境變數！請確認 FINMIND_API_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

# ─── 初始化 ───
FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 撈最近 5 天的資料（確保補到假日空缺）
TODAY = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")


def fetch_finmind(dataset, params=None):
    """通用 FinMind API 請求"""
    if params is None:
        params = {}
    params["dataset"] = dataset
    headers = {"Authorization": f"Bearer {FINMIND_TOKEN}"}

    try:
        resp = requests.get(FINMIND_BASE, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("msg") != "success":
            print(f"  ⚠ FinMind 回傳錯誤: {data.get('msg', '未知')}")
            return []

        return data.get("data", [])
    except Exception as e:
        print(f"  ❌ 請求失敗: {e}")
        return []


def get_etf_ids():
    """從 Supabase 取得所有要追蹤的 ETF 代碼"""
    result = supabase.table("etf_info").select("id").execute()
    return [row["id"] for row in result.data] if result.data else []


def sync_prices(etf_ids):
    """同步每日股價"""
    print("\n📊 同步股價...")
    total = 0

    for etf_id in etf_ids:
        data = fetch_finmind("TaiwanStockPrice", {
            "data_id": etf_id,
            "start_date": START_DATE,
        })

        if not data:
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
                supabase.table("etf_daily_price").upsert(
                    rows, on_conflict="etf_id,date"
                ).execute()
                total += len(rows)
                print(f"  ✅ {etf_id}: {len(rows)} 筆")
            except Exception as e:
                print(f"  ❌ {etf_id}: {e}")

    return total


def sync_valuations(etf_ids):
    """同步估值指標（PER / PBR / 殖利率）"""
    print("\n📈 同步估值指標...")
    total = 0

    for etf_id in etf_ids:
        data = fetch_finmind("TaiwanStockPER", {
            "data_id": etf_id,
            "start_date": START_DATE,
        })

        if not data:
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
                supabase.table("etf_valuation").upsert(
                    rows, on_conflict="etf_id,date"
                ).execute()
                total += len(rows)
                print(f"  ✅ {etf_id}: {len(rows)} 筆")
            except Exception as e:
                print(f"  ❌ {etf_id}: {e}")

    return total


def sync_institutional(etf_ids):
    """同步三大法人買賣超"""
    print("\n🏛️ 同步法人買賣超...")
    total = 0

    for etf_id in etf_ids:
        data = fetch_finmind("TaiwanStockInstitutionalInvestorsBuySell", {
            "data_id": etf_id,
            "start_date": START_DATE,
        })

        if not data:
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
                supabase.table("etf_institutional").upsert(
                    rows, on_conflict="etf_id,date,investor_type"
                ).execute()
                total += len(rows)
                print(f"  ✅ {etf_id}: {len(rows)} 筆")
            except Exception as e:
                print(f"  ❌ {etf_id}: {e}")

    return total


def sync_dividends(etf_ids):
    """同步配息紀錄（不需要每天跑，但跑了也不會重複）"""
    print("\n💰 同步配息紀錄...")
    total = 0

    for etf_id in etf_ids:
        data = fetch_finmind("TaiwanStockDividend", {
            "data_id": etf_id,
            "start_date": "2020-01-01",
        })

        if not data:
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
                print(f"  ✅ {etf_id}: {len(rows)} 筆")
            except Exception as e:
                print(f"  ❌ {etf_id}: {e}")

    return total


# ─── 主程式 ───
if __name__ == "__main__":
    print("=" * 50)
    print(f"🚀 ETF 資料同步開始")
    print(f"📅 日期範圍: {START_DATE} ~ {TODAY}")
    print("=" * 50)

    # 取得要同步的 ETF 清單
    etf_ids = get_etf_ids()
    print(f"\n📋 共 {len(etf_ids)} 檔 ETF: {', '.join(etf_ids)}")

    if not etf_ids:
        print("❌ Supabase 的 etf_info 表是空的，請先新增 ETF 資料")
        sys.exit(1)

    # 逐項同步
    price_count = sync_prices(etf_ids)
    val_count = sync_valuations(etf_ids)
    inst_count = sync_institutional(etf_ids)
    div_count = sync_dividends(etf_ids)

    # 結果摘要
    print("\n" + "=" * 50)
    print("✅ 同步完成！")
    print(f"   股價:   {price_count} 筆")
    print(f"   估值:   {val_count} 筆")
    print(f"   法人:   {inst_count} 筆")
    print(f"   配息:   {div_count} 筆")
    print("=" * 50)
