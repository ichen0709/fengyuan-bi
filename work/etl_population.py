# /// script
# requires-python = ">=3.10"
# dependencies = ["openpyxl", "pandas"]
# ///
"""把豐原區 115年09月各里人口結構(男、女兩份報表)轉成長表 CSV。

「全部/計」那份只用於驗證(scripts/validate_fengyuan.py),不放進輸出。

用法: uv run work/etl_population.py [輸出.csv]
"""
import re
import sys
from pathlib import Path

import pandas as pd

RAW = Path("raw")
SOURCES = {
    "男": RAW / "fengyuan_2026-09_population_male.xlsx",
    "女": RAW / "fengyuan_2026-09_population_female.xlsx",
}
DST = Path(sys.argv[1] if len(sys.argv) > 1 else "work/population_115-09.csv")


def read_report(path: Path) -> pd.DataFrame:
    """第 1 列空白、第 2 列是合併標題、第 3 列才是表頭。"""
    df = pd.read_excel(path, sheet_name=0, header=None, skiprows=2, dtype=object)
    df.columns = df.iloc[0].astype(str).str.strip()
    return df.iloc[1:].dropna(how="all").reset_index(drop=True)


def parse_age(label: str):
    m = re.fullmatch(r"(\d+)-(\d+)歲", label)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r"(\d+)歲以上", label)
    if m:
        return int(m.group(1)), None
    raise ValueError(f"無法解析年齡組: {label!r}")


frames = []
for gender, path in SOURCES.items():
    df = read_report(path)
    # 報表上的性別欄必須和檔案用途一致,否則寧可停下來
    found = set(df["性別"])
    if found != {gender}:
        raise SystemExit(f"{path} 的性別欄是 {found},預期 {{{gender!r}}}")
    # 「全部」是整區合計,不是一個里,不輸出
    df = df[df["里名"] != "全部"]
    age_cols = [c for c in df.columns if c not in ("區域別", "里名", "性別", "總計")]
    long = df.melt(
        id_vars=["區域別", "里名", "性別"],
        value_vars=age_cols,
        var_name="age_group_raw",
        value_name="count",
    ).rename(columns={"區域別": "district", "里名": "village", "性別": "gender"})
    # melt 是依欄位排列,改回「里 × 年齡組」並保持報表順序
    long["_v"] = long.groupby("village", sort=False).ngroup()
    long["_a"] = long["age_group_raw"].map({c: i for i, c in enumerate(age_cols)})
    long = long.sort_values(["_v", "_a"]).drop(columns=["_v", "_a"])
    frames.append(long)

long = pd.concat(frames, ignore_index=True)
long["age_group"] = long["age_group_raw"].str.replace("合計", "", regex=False)
ages = long["age_group"].map(parse_age)
long["age_min"] = [a[0] for a in ages]
long["age_max"] = pd.array([a[1] for a in ages], dtype="Int64")
long["count"] = pd.to_numeric(long["count"]).astype("Int64")

out = long[["district", "village", "gender", "age_group", "age_min", "age_max", "count"]]
DST.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(DST, index=False, encoding="utf-8-sig")
print(f"寫出 {len(out)} 列 -> {DST}")
