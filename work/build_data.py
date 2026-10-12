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
assert set(df["gender"]) == {"男", "女"}, set(df["gender"])

# 0-14 歲 = 前 3 組, 15-64 歲 = 中間 10 組, 65 歲以上 = 其餘 8 組
SLICES = {"young": slice(0, 3), "working": slice(3, 13), "old": slice(13, 21)}
assert age_groups[2] == "10-14歲" and age_groups[12] == "60-64歲"
assert age_groups[13] == "65-69歲" and age_groups[-1] == "100歲以上"


def ratio(num, den):
    """分母為 0 時回傳 None(輸出成 null),不除以零。"""
    return round(num / den * 100, 1) if den else None


def bands(counts: list) -> dict:
    return {k: sum(counts[s]) for k, s in SLICES.items()}


def summarize(male: list, female: list) -> dict:
    both = [m + f for m, f in zip(male, female)]
    b, bm, bf = bands(both), bands(male), bands(female)
    return {
        "total": sum(both),
        "male": sum(male),
        "female": sum(female),
        "bands": {"all": b, "male": bm, "female": bf},
        "aging_index": ratio(b["old"], b["young"]),
        "dependency_ratio": ratio(b["young"] + b["old"], b["working"]),
        "sex_ratio": ratio(sum(male), sum(female)),
        "old_sex_ratio": ratio(bm["old"], bf["old"]),
        "counts": {"男": male, "女": female},
    }


def counts_of(g: pd.DataFrame, gender: str) -> list:
    s = g[g["gender"] == gender].set_index("age_group")["count"]
    return [int(s[a]) for a in age_groups]


villages = []
for name, g in df.groupby("village", sort=False):
    villages.append({"name": name, **summarize(counts_of(g, "男"), counts_of(g, "女"))})

district = summarize(
    [sum(v["counts"]["男"][i] for v in villages) for i in range(21)],
    [sum(v["counts"]["女"][i] for v in villages) for i in range(21)],
)

data = {
    "title": "臺中市豐原區 115年09月人口結構",
    "district": df["district"].iloc[0],
    "age_groups": age_groups,
    "age_bands": {"young": "0-14歲", "working": "15-64歲", "old": "65歲以上"},
    "district_total": district,
    "villages": villages,
}

DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(
    "window.FENGYUAN_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
    encoding="utf-8",
)
d = district
print(f"寫出 {DST} ({DST.stat().st_size:,} bytes), {len(villages)} 個里")
print({k: d[k] for k in ("total", "male", "female", "aging_index", "dependency_ratio", "sex_ratio", "old_sex_ratio")})
print(d["bands"])
