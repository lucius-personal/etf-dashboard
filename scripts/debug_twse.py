"""快速查看 TWSE OpenAPI 回傳的欄位和代碼格式"""

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("🔍 檢查 TWSE OpenAPI 資料格式...\n")

resp = requests.get(
    "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d",
    timeout=30,
    verify=False,
)

data = resp.json()
print(f"共 {len(data)} 筆資料\n")

# 印出第一筆的所有欄位
print("=== 第一筆資料的所有欄位 ===")
for key, val in data[0].items():
    print(f"  {key}: '{val}'")

# 找出所有可能是 ETF 的資料（代碼以 00 開頭或是 0050 等）
print("\n=== 搜尋 ETF 相關代碼 ===")
targets = ["0050", "009816", "0056", "00878", "00919", "00929", "00679B"]
all_codes = set()

for d in data:
    # 印出所有欄位中包含目標代碼的
    for key, val in d.items():
        val_str = str(val).strip()
        if val_str in targets:
            print(f"  找到！欄位 '{key}' = '{val_str}'")
            print(f"  完整資料: {d}")
            print()
        all_codes.add(val_str)

# 印出前 20 個代碼看格式
print("\n=== 前 20 個 Code 欄位值 ===")
codes = [str(d.get("Code", "")).strip() for d in data[:20]]
for c in codes:
    print(f"  '{c}' (len={len(c)})")

# 搜尋包含 0050 的任何欄位值
print("\n=== 在所有欄位中搜尋 '0050' ===")
for d in data:
    for key, val in d.items():
        if "0050" in str(val):
            print(f"  欄位 '{key}' = '{val}'")
            break
    else:
        continue
    break

print("\n完成！")
