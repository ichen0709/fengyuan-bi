# /// script
# requires-python = ">=3.10"
# dependencies = ["openpyxl", "pandas"]
# ///
"""驗證豐原區人口長表 CSV 與原始 xlsx 是否一致。

用法: uv run scripts/validate_fengyuan.py work/population_115-09.csv [raw.xlsx]
"""
import sys
from pathlib import Path

import pandas as pd

csv_path = Path(sys.argv[1] if len(sys.argv) > 1 else "work/population_115-09.csv")
xlsx_path = Path(sys.argv[2] if len(sys.argv) > 2 else "raw/fengyuan_2026-09_population.xlsx")

out = pd.read_csv(csv_path, encoding="utf-8-sig")

raw = pd.read_excel(xlsx_path, sheet_name=0, header=None, skiprows=2, dtype=object)
raw.columns = raw.iloc[0].astype(str).str.strip()
raw = raw.iloc[1:].dropna(how="all")
total_row = raw[raw["里名"] == "全部"]
villages_raw = raw[raw["里名"] != "全部"]
village_totals = villages_raw.set_index("里名")["總計"].astype(int)

errors = []

# 1. 里的數量
n_vil = out["village"].nunique()
if n_vil != 36:
    errors.append(f"1. 里的數量應為 36,實際 {n_vil}")

# 2. 筆數
if len(out) != 36 * 21:
    errors.append(f"2. 筆數應為 756,實際 {len(out)}")

# 3. 各里年齡組加總 == 該里總計
sums = out.groupby("village")["count"].sum()
for v, expected in village_totals.items():
    got = sums.get(v)
    if got != expected:
        errors.append(f"3. {v}: 年齡組加總 {got} != 總計 {expected}")
for v in sums.index.difference(village_totals.index):
    errors.append(f"3. {v}: 在 CSV 中但不在原始報表")

# 4. 36 個里總計 == 「全部」
if len(total_row) != 1:
    errors.append(f"4. 原始報表「全部」列應有 1 列,實際 {len(total_row)}")
else:
    all_total = int(total_row["總計"].iloc[0])
    vsum = int(village_totals.sum())
    if vsum != all_total:
        errors.append(f"4. 各里總計加總 {vsum} != 「全部」總計 {all_total}")
    if int(out["count"].sum()) != all_total:
        errors.append(f"4. CSV count 加總 {int(out['count'].sum())} != 「全部」總計 {all_total}")

# 5. 沒有負數、沒有空值(age_max 的「100歲以上」依規則可為空)
required = ["district", "village", "age_group", "age_min", "count"]
for col in required:
    nulls = out[out[col].isna()]
    if len(nulls):
        errors.append(f"5. 欄位 {col} 有 {len(nulls)} 個空值")
bad_max = out[out["age_max"].isna() & (out["age_group"] != "100歲以上")]
if len(bad_max):
    errors.append(f"5. age_max 空值只應出現在「100歲以上」,但有 {len(bad_max)} 列不是")
neg = out[out["count"] < 0]
if len(neg):
    errors.append(f"5. count 有負數: {neg[['village', 'age_group', 'count']].to_dict('records')}")

if errors:
    print("驗證失敗:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("全部通過")
