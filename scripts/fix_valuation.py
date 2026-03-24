"""
單獨補估值資料（PER / PBR / 殖利率）
從 TWSE OpenAPI 撈取，跳過 SSL 憑證檢查
"""

import os
import sys
import requests
import urllib3
from datetime import datetime

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("缺少環境變數！")
    sys.exit(1)

SUPABASE_REST = f"{SUPABASE_URL}/rest/v1"
TODAY = datetime.now().strftime("%Y-%m-%d")


def supa_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def get_etf_ids():
    resp = requests.get(
        f"{SUPABASE_REST}/etf_info?select=id",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    return [r["id"] for r in resp.json()] if resp.status_code == 200 else []


def upsert(table, rows):
    if not rows:
        return 0
    url = f"{SUPABASE_REST}/{table}?on_conflict=etf_id,date"
    resp = requests.post(url, headers=supa_headers(), json=rows, timeout=30)
    return len(rows) if resp.status_code in (200, 201) else 0


print("=" * 50)
print("📈 補估值資料（TWSE OpenAPI）")
print("=" * 50)

etf_ids = get_etf_ids()
print(f"📋 追蹤 {len(etf_ids)} 檔 ETF")

total = 0

# ─── 上市 ETF（TWSE）───
print("\n🔵 撈取上市 ETF 估值...")
try:
    resp = requests.get(
        "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d",
        timeout=30,
        verify=False,  # 跳過 SSL
    )
    if resp.status_code == 200:
        data = resp.json()
        rows = []
        matched = []
        for d in data:
            code = d.get("Code", "")
            if code in etf_ids:
                yld = d.get("DividendYield", "")
                per = d.get("PEratio", "")
                pbr = d.get("PBratio", "")
                rows.append({
                    "etf_id": code,
                    "date": TODAY,
                    "dividend_yield": float(yld) if yld and yld.strip() and yld != "-" else None,
                    "per": float(per) if per and per.strip() and per != "-" else None,
                    "pbr": float(pbr) if pbr and pbr.strip() and pbr != "-" else None,
                })
                matched.append(code)

        if rows:
            c = upsert("etf_valuation", rows)
            total += c
            print(f"  ✅ 找到 {len(rows)} 檔: {', '.join(matched)}")
            for r in rows:
                yld = r['dividend_yield'] or '-'
                per = r['per'] or '-'
                pbr = r['pbr'] or '-'
                print(f"     {r['etf_id']}: 殖利率={yld}%, PER={per}, PBR={pbr}")
        else:
            print("  ⚠ 沒有匹配到追蹤的 ETF")
            print(f"  (TWSE 回傳 {len(data)} 筆資料，但沒有你追蹤的代碼)")
    else:
        print(f"  ❌ HTTP {resp.status_code}")
except Exception as e:
    print(f"  ❌ {e}")

# ─── 上櫃 ETF（TPEx）───
print("\n🟢 撈取上櫃 ETF 估值...")
try:
    resp = requests.get(
        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
        timeout=30,
        verify=False,
    )
    if resp.status_code == 200:
        data = resp.json()
        rows = []
        matched = []
        for d in data:
            code = d.get("SecuritiesCompanyCode", "")
            if code in etf_ids:
                yld = d.get("DividendYield", "")
                per = d.get("PriceEarningRatio", "")
                pbr = d.get("PriceBookRatio", "")
                rows.append({
                    "etf_id": code,
                    "date": TODAY,
                    "dividend_yield": float(yld) if yld and yld.strip() and yld != "-" else None,
                    "per": float(per) if per and per.strip() and per != "-" else None,
                    "pbr": float(pbr) if pbr and pbr.strip() and pbr != "-" else None,
                })
                matched.append(code)

        if rows:
            c = upsert("etf_valuation", rows)
            total += c
            print(f"  ✅ 找到 {len(rows)} 檔: {', '.join(matched)}")
        else:
            print("  ⚠ 沒有匹配到追蹤的 ETF（上櫃）")
    else:
        print(f"  ❌ HTTP {resp.status_code}")
except Exception as e:
    print(f"  ❌ {e}")

print(f"\n{'=' * 50}")
print(f"✅ 估值回補完成！共 {total} 筆")
print(f"{'=' * 50}")
