# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""把 work/population_115-09.csv 整理成網頁可直接載入的 docs/data.js。

用法: uv run work/build_data.py [輸入.csv] [輸出.js]
"""
import json
import sys
from pathlib import Path

import pandas as pd

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "work/population_115-09.csv")
DST = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/data.js")

df = pd.read_csv(SRC, encoding="utf-8-sig")
age_groups = list(dict.fromkeys(df["age_group"]))  # 保持報表順序
assert len(age_groups) == 21, age_groups

# 0-14 歲 = 前 3 組, 15-64 歲 = 中間 10 組, 65 歲以上 = 其餘 8 組
young_groups = age_groups[:3]
working_groups = age_groups[3:13]
old_groups = age_groups[13:]
assert young_groups[-1] == "10-14歲" and working_groups[-1] == "60-64歲"
assert old_groups[0] == "65-69歲" and old_groups[-1] == "100歲以上"


def summarize(counts: dict) -> dict:
    young = sum(counts[g] for g in young_groups)
    working = sum(counts[g] for g in working_groups)
    old = sum(counts[g] for g in old_groups)
    return {
        "total": young + working + old,
        "young": young,
        "working": working,
        "old": old,
        "aging_index": round(old / young * 100, 1) if young else None,
        "dependency_ratio": round((young + old) / working * 100, 1) if working else None,
        "counts": [counts[g] for g in age_groups],
    }


villages = []
for name, g in df.groupby("village", sort=False):
    counts = {int_k: int(v) for int_k, v in zip(g["age_group"], g["count"])}
    villages.append({"name": name, **summarize(counts)})

district_counts = {g: int(df.loc[df["age_group"] == g, "count"].sum()) for g in age_groups}
data = {
    "title": "臺中市豐原區 115年09月人口結構",
    "district": df["district"].iloc[0],
    "age_groups": age_groups,
    "age_bands": {"young": "0-14歲", "working": "15-64歲", "old": "65歲以上"},
    "district_total": summarize(district_counts),
    "villages": villages,
}

DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(
    "window.FENGYUAN_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
    encoding="utf-8",
)
d = data["district_total"]
print(f"寫出 {DST} ({DST.stat().st_size:,} bytes), {len(villages)} 個里")
print({k: d[k] for k in ("total", "young", "working", "old", "aging_index", "dependency_ratio")})
