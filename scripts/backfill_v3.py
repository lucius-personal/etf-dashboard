"""
台股 ETF 歷史資料回補腳本 v3
修正：upsert 衝突處理 + TWSE OpenAPI 撈估值
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
    print("缺少環境變數！")
    sys.exit(1)

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
SUPABASE_REST = f"{SUPABASE_URL}/rest/v1"
TODAY = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
DELAY = 3


def supa_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


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
            return []
        return data.get("data", [])
    except Exception as e:
        print(f"  ❌ FinMind: {e}")
        return []


def upsert(table, rows, conflict_cols):
    """寫入 Supabase，重複的自動更新"""
    if not rows:
        return 0
    total = 0
    url = f"{SUPABASE_REST}/{table}?on_conflict={conflict_cols}"
    for i in range(0, len(rows), 50):
        batch = rows[i:i+50]
        try:
            resp = requests.post(url, headers=supa_headers(), json=batch, timeout=30)
            if resp.status_code in (200, 201):
                total += len(batch)
            else:
                # 有時 Supabase 回 409 但資料其實有寫入，嘗試改用 PUT
                resp2 = requests.post(
                    f"{SUPABASE_REST}/{table}",
                    headers={**supa_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                    json=batch,
                    timeout=30,
                )
                if resp2.status_code in (200, 201):
                    total += len(batch)
                else:
                    print(f"  ⚠ {table} 寫入失敗: {resp.status_code}")
        except Exception as e:
            print(f"  ❌ {e}")
    return total


def get_etf_ids():
    resp = requests.get(
        f"{SUPABASE_REST}/etf_info?select=id",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
        timeout=15,
    )
    return [row["id"] for row in resp.json()] if resp.status_code == 200 else []


# ─── 股價 ───
def backfill_prices(etf_ids):
    print("\n" + "=" * 50)
    print("📊 回補股價...")
    print("=" * 50)
    total = 0
    for i, eid in enumerate(etf_ids):
        print(f"  [{i+1}/{len(etf_ids)}] {eid}...", end=" ")
        data = fetch_finmind("TaiwanStockPrice", {"data_id": eid, "start_date": START_DATE})
        if not data:
            print("無資料"); time.sleep(DELAY); continue
        rows = [{"etf_id": eid, "date": d["date"], "open": d.get("open"), "high": d.get("max"),
                 "low": d.get("min"), "close": d.get("close"), "volume": d.get("Trading_Volume"),
                 "spread": d.get("spread")} for d in data]
        c = upsert("etf_daily_price", rows, "etf_id,date")
        total += c; print(f"✅ {c} 筆"); time.sleep(DELAY)
    return total


# ─── 估值：先試 FinMind，沒有的話用 TWSE OpenAPI ───
def backfill_valuations(etf_ids):
    print("\n" + "=" * 50)
    print("📈 回補估值（PER / PBR / 殖利率）...")
    print("=" * 50)
    total = 0

    # 方法 1: 嘗試 FinMind
    for i, eid in enumerate(etf_ids):
        print(f"  [{i+1}/{len(etf_ids)}] {eid} (FinMind)...", end=" ")
        data = fetch_finmind("TaiwanStockPER", {"data_id": eid, "start_date": START_DATE})
        if data:
            rows = [{"etf_id": eid, "date": d["date"], "dividend_yield": d.get("dividend_yield"),
                     "per": d.get("PER"), "pbr": d.get("PBR")} for d in data]
            c = upsert("etf_valuation", rows, "etf_id,date")
            total += c; print(f"✅ {c} 筆")
        else:
            print("無資料，改用 TWSE...")
        time.sleep(DELAY)

    # 方法 2: TWSE OpenAPI 撈當日全部 ETF 的 PER/殖利率
    print("\n  📡 從 TWSE OpenAPI 撈即時估值...")
    try:
        # 上市 ETF
        twse_resp = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d",
            timeout=30,
        )
        if twse_resp.status_code == 200:
            twse_data = twse_resp.json()
            today_str = TODAY
            rows = []
            for d in twse_data:
                code = d.get("Code", "")
                if code in etf_ids:
                    yld = d.get("DividendYield", "")
                    per = d.get("PEratio", "")
                    pbr = d.get("PBratio", "")
                    rows.append({
                        "etf_id": code,
                        "date": today_str,
                        "dividend_yield": float(yld) if yld and yld != "-" else None,
                        "per": float(per) if per and per != "-" else None,
                        "pbr": float(pbr) if pbr and pbr != "-" else None,
                    })
            if rows:
                c = upsert("etf_valuation", rows, "etf_id,date")
                total += c
                print(f"  ✅ TWSE 上市: {c} 筆")
            else:
                print(f"  ⚠ TWSE 上市: 無匹配的 ETF")
        else:
            print(f"  ⚠ TWSE 上市 API 失敗: {twse_resp.status_code}")
    except Exception as e:
        print(f"  ❌ TWSE 上市: {e}")

    time.sleep(1)

    try:
        # 上櫃 ETF
        tpex_resp = requests.get(
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
            timeout=30,
        )
        if tpex_resp.status_code == 200:
            tpex_data = tpex_resp.json()
            today_str = TODAY
            rows = []
            for d in tpex_data:
                code = d.get("SecuritiesCompanyCode", "")
                if code in etf_ids:
                    yld = d.get("DividendYield", "")
                    per = d.get("PriceEarningRatio", "")
                    pbr = d.get("PriceBookRatio", "")
                    rows.append({
                        "etf_id": code,
                        "date": today_str,
                        "dividend_yield": float(yld) if yld and yld != "-" else None,
                        "per": float(per) if per and per != "-" else None,
                        "pbr": float(pbr) if pbr and pbr != "-" else None,
                    })
            if rows:
                c = upsert("etf_valuation", rows, "etf_id,date")
                total += c
                print(f"  ✅ TWSE 上櫃: {c} 筆")
        else:
            print(f"  ⚠ TWSE 上櫃 API 失敗: {tpex_resp.status_code}")
    except Exception as e:
        print(f"  ❌ TWSE 上櫃: {e}")

    return total


# ─── 法人 ───
def backfill_institutional(etf_ids):
    print("\n" + "=" * 50)
    print("🏛️ 回補三大法人買賣超...")
    print("=" * 50)
    total = 0
    for i, eid in enumerate(etf_ids):
        print(f"  [{i+1}/{len(etf_ids)}] {eid}...", end=" ")
        data = fetch_finmind("TaiwanStockInstitutionalInvestorsBuySell", {"data_id": eid, "start_date": START_DATE})
        if not data:
            print("無資料"); time.sleep(DELAY); continue
        rows = [{"etf_id": eid, "date": d["date"], "investor_type": d.get("name", ""),
                 "buy": d.get("buy", 0), "sell": d.get("sell", 0)} for d in data]
        c = upsert("etf_institutional", rows, "etf_id,date,investor_type")
        total += c; print(f"✅ {c} 筆"); time.sleep(DELAY)
    return total


# ─── 配息 ───
def backfill_dividends(etf_ids):
    print("\n" + "=" * 50)
    print("💰 回補配息紀錄...")
    print("=" * 50)
    total = 0
    for i, eid in enumerate(etf_ids):
        print(f"  [{i+1}/{len(etf_ids)}] {eid}...", end=" ")
        data = fetch_finmind("TaiwanStockDividend", {"data_id": eid, "start_date": "2020-01-01"})
        if not data:
            print("無資料"); time.sleep(DELAY); continue
        rows = []
        for d in data:
            ex = d.get("date")
            if not ex: continue
            rows.append({"etf_id": eid, "ex_date": ex,
                         "cash_dividend": d.get("CashEarningsDistribution", 0),
                         "stock_dividend": d.get("StockEarningsDistribution", 0),
                         "year": d.get("year", "")})
        c = upsert("etf_dividend", rows, "etf_id,ex_date")
        total += c; print(f"✅ {c} 筆"); time.sleep(DELAY)
    return total


# ─── 主程式 ───
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ETF 歷史資料回補 v3")
    print(f"📅 範圍: {START_DATE} ~ {TODAY}")
    print("=" * 60)

    etf_ids = get_etf_ids()
    print(f"\n📋 共 {len(etf_ids)} 檔 ETF: {', '.join(etf_ids)}")

    if not etf_ids:
        print("❌ etf_info 表是空的！"); sys.exit(1)

    p = backfill_prices(etf_ids)
    v = backfill_valuations(etf_ids)
    i = backfill_institutional(etf_ids)
    d = backfill_dividends(etf_ids)

    print("\n" + "=" * 60)
    print("✅ 回補完成！")
    print(f"   股價: {p} 筆")
    print(f"   估值: {v} 筆")
    print(f"   法人: {i} 筆")
    print(f"   配息: {d} 筆")
    print("=" * 60)
    print("\n🎉 重新整理儀表板看看！")
