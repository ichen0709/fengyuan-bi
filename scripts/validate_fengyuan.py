# /// script
# requires-python = ">=3.10"
# dependencies = ["openpyxl", "pandas"]
# ///
"""驗證豐原區人口長表 CSV 與三份原始 xlsx(全部/男/女)是否一致。

用法: uv run scripts/validate_fengyuan.py work/population_115-09.csv
"""
import sys
from pathlib import Path

import pandas as pd

csv_path = Path(sys.argv[1] if len(sys.argv) > 1 else "work/population_115-09.csv")
RAW = Path("raw")
FILES = {
    "all": RAW / "fengyuan_2026-09_population_all.xlsx",
    "男": RAW / "fengyuan_2026-09_population_male.xlsx",
    "女": RAW / "fengyuan_2026-09_population_female.xlsx",
}
EXPECTED_TOTAL = 160762

out = pd.read_csv(csv_path, encoding="utf-8-sig")


def read_report(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, header=None, skiprows=2, dtype=object)
    df.columns = df.iloc[0].astype(str).str.strip()
    return df.iloc[1:].dropna(how="all").reset_index(drop=True)


reports = {k: read_report(p) for k, p in FILES.items()}
age_cols = [c for c in reports["all"].columns if c not in ("區域別", "里名", "性別", "總計")]


def long_counts(df: pd.DataFrame) -> pd.DataFrame:
    """里 × 年齡組 的人數(不含「全部」列),年齡組已去掉「合計」。"""
    v = df[df["里名"] != "全部"].set_index("里名")[age_cols].astype(int)
    v.columns = [c.replace("合計", "") for c in v.columns]
    return v


errors = []

# 1. 里的數量
n_vil = out["village"].nunique()
if n_vil != 36:
    errors.append(f"1. 里的數量應為 36,實際 {n_vil}")

# 2. 筆數
if len(out) != 36 * 2 * 21:
    errors.append(f"2. 筆數應為 1512,實際 {len(out)}")
if set(out["gender"]) != {"男", "女"}:
    errors.append(f"2. gender 應只有 男、女,實際 {sorted(set(out['gender']))}")

dups = out[out.duplicated(["village", "gender", "age_group"], keep=False)]
for _, r in dups.drop_duplicates(["village", "gender", "age_group"]).iterrows():
    errors.append(f"2. 重複的列: {r['village']} {r['gender']} {r['age_group']}")

# 輸出轉成 里 × 年齡組 的寬表,方便和各份報表比對(重複列已在上面回報)
wide = {
    g: out[out["gender"] == g].pivot_table(
        index="village", columns="age_group", values="count", aggfunc="first"
    )
    for g in ("男", "女")
}
all_counts = long_counts(reports["all"])

# 3. 每個里每個年齡組: 男 + 女 == 全部份
try:
    summed = (wide["男"] + wide["女"]).reindex(index=all_counts.index, columns=all_counts.columns)
    diff = summed != all_counts
    for v, a in zip(*diff.to_numpy().nonzero()):
        vil, age = all_counts.index[v], all_counts.columns[a]
        errors.append(
            f"3. {vil} {age}: 男 {wide['男'].loc[vil, age]} + 女 {wide['女'].loc[vil, age]}"
            f" != 全部份 {all_counts.loc[vil, age]}"
        )
    if summed.isna().to_numpy().any():
        errors.append("3. 男 + 女 對不上全部份的里或年齡組(有缺漏)")
except Exception as e:  # 結構錯誤時也要列出來,而不是整個崩潰
    errors.append(f"3. 無法比對男 + 女 與全部份: {e}")

# 4. 每個里男、女各年齡組加起來 == 各自檔案的「總計」
for g in ("男", "女"):
    rep = reports[g]
    totals = rep[rep["里名"] != "全部"].set_index("里名")["總計"].astype(int)
    sums = out[out["gender"] == g].groupby("village")["count"].sum()
    for v, expected in totals.items():
        got = sums.get(v)
        if got != expected:
            errors.append(f"4. {v} {g}: 年齡組加總 {got} != 總計 {expected}")

# 5. 36 個里加總 == 各檔「全部」列,男 + 女 == 160762
grand = {}
for g in ("男", "女"):
    rep = reports[g]
    row = rep[rep["里名"] == "全部"]
    if len(row) != 1:
        errors.append(f"5. {g} 檔「全部」列應有 1 列,實際 {len(row)}")
        continue
    grand[g] = int(row["總計"].iloc[0])
    got = int(out.loc[out["gender"] == g, "count"].sum())
    if got != grand[g]:
        errors.append(f"5. {g}: 36 個里加總 {got} != 「全部」列總計 {grand[g]}")
if len(grand) == 2 and sum(grand.values()) != EXPECTED_TOTAL:
    errors.append(f"5. 男 {grand['男']} + 女 {grand['女']} != {EXPECTED_TOTAL}")
if int(out["count"].sum()) != EXPECTED_TOTAL:
    errors.append(f"5. CSV 全部人數加總 {int(out['count'].sum())} != {EXPECTED_TOTAL}")

# 6. 沒有負數、沒有空值(「100歲以上」的 age_max 依規則為空)
for col in ["district", "village", "gender", "age_group", "age_min", "count"]:
    n = int(out[col].isna().sum())
    if n:
        errors.append(f"6. 欄位 {col} 有 {n} 個空值")
bad_max = out[out["age_max"].isna() & (out["age_group"] != "100歲以上")]
if len(bad_max):
    errors.append(f"6. age_max 空值只應出現在「100歲以上」,但有 {len(bad_max)} 列不是")
neg = out[out["count"] < 0]
if len(neg):
    errors.append(f"6. count 有負數: {neg[['village', 'gender', 'age_group', 'count']].to_dict('records')}")

if errors:
    print("驗證失敗:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("全部通過")
