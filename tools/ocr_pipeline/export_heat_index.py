#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导出可直接导入 App 的热量索引。

只保留：食物名称非空 + 自动校验通过（热量与宏量营养素自洽、kcal/kJ 一致）的记录。

用法：
  python export_heat_index.py --src output/heat_index/heat_index.jsonl --out output/heat_index/app
"""

import argparse
import csv
import json
import re
from pathlib import Path


def clean_name(name: str) -> str:
    name = (name or "").strip()
    for src, dst in (("【", "["), ("】", "]"), ("［", "["), ("］", "]")):
        name = name.replace(src, dst)
    return re.sub(r"\s+", " ", name).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    kept = []
    dropped_name = dropped_valid = 0
    with open(src, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            name = (rec.get("food_name") or "").strip()
            ok = bool((rec.get("validation") or {}).get("ok"))
            if not name:
                dropped_name += 1
                continue
            if not ok:
                dropped_valid += 1
                continue
            kept.append(rec)

    # 按食物编码排序，方便后续增量维护
    # 同一食物编码只保留一条（OCR 变体去重），优先保留名称更工整的一条
    best = {}
    for rec in kept:
        rec["food_name"] = clean_name(rec["food_name"])
        code = str(rec["food_code"])
        old = best.get(code)
        if old is None or len(rec["food_name"]) < len(old["food_name"]):
            best[code] = rec
    dedup_count = len(kept) - len(best)
    kept = sorted(best.values(), key=lambda r: str(r["food_code"]))

    jsonl_path = out / "app_heat_index.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for rec in kept:
            item = {
                "food_code": rec["food_code"],
                "food_name": rec["food_name"],
                "energy_kcal": rec["energy_kcal"],
                "energy_kj": rec.get("energy_kj"),
                "water_g": rec.get("water_g"),
                "protein_g": rec.get("protein_g"),
                "fat_g": rec.get("fat_g"),
                "carb_g": rec.get("carb_g"),
                "source_page": rec.get("page"),
                "source_book": rec.get("source"),
            }
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    csv_path = out / "app_heat_index.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["food_code", "food_name", "energy_kcal", "energy_kj", "water_g", "protein_g", "fat_g", "carb_g", "source_page"]
        )
        for rec in kept:
            writer.writerow([
                rec["food_code"],
                rec["food_name"],
                rec["energy_kcal"],
                rec.get("energy_kj", ""),
                rec.get("water_g", ""),
                rec.get("protein_g", ""),
                rec.get("fat_g", ""),
                rec.get("carb_g", ""),
                rec.get("page", ""),
            ])

    print(f"保留：{len(kept)} 条")
    print(f"同编码去重：{dedup_count} 条")
    print(f"剔除（名称为空）：{dropped_name} 条")
    print(f"剔除（校验未过）：{dropped_valid} 条")
    print(f"输出：{csv_path}")
    print(f"输出：{jsonl_path}")

    cats = {}
    for rec in kept:
        key = str(rec["food_code"])[:2]
        cats[key] = cats.get(key, 0) + 1
    print("类别分布：" + "，".join(f"{k}={v}" for k, v in sorted(cats.items())))


if __name__ == "__main__":
    main()
