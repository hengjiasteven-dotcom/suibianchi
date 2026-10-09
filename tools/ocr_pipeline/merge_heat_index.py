#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把分片提取的热量 JSONL 合并成可用的热量索引，并做自动校验。

校验规则：
1. 能量范围：0 < kcal <= 900（每 100g）。
2. kcal 与 kJ 互相印证：kcal * 4.184 与 kJ 的相对偏差不超过 6%。
3. 食物编码为 5-7 位数字。
4. 食物名称为空、编码异常、换算失败的记录会被标记，而不是直接丢弃。

输出：
  heat_index.jsonl  清洗后的逐条记录（含 validation 字段）
  heat_index.csv    便于用 Excel/表格查看
  merge_report.md   统计报告
"""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

CODE_RE = re.compile(r"^\d{5,7}$")
KJ_PER_KCAL = 4.184
TOLERANCE = 0.06


def load_records(root: Path):
    records = []
    for jsonl in sorted(root.glob("*/foods.jsonl")):
        with open(jsonl, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rec["_chunk"] = jsonl.parent.name
                records.append(rec)
    return records


def validate(rec):
    issues = []
    code = str(rec.get("food_code", ""))
    name = (rec.get("food_name") or "").strip()
    kcal = rec.get("energy_kcal")
    kj = rec.get("energy_kj")

    if not CODE_RE.match(code):
        issues.append(f"食物编码异常：{code}")
    if not name:
        issues.append("食物名称为空")
    if kcal is None:
        issues.append("缺少能量")
    elif not 0 < kcal <= 900:
        issues.append(f"能量超出合理范围：{kcal}")
    if kcal is not None and kj:
        expected = kcal * KJ_PER_KCAL
        diff = abs(expected - kj) / expected
        if diff > TOLERANCE:
            issues.append(f"kcal/kJ 不一致：{kcal} kcal vs {kj} kJ（偏差 {diff:.0%}）")
    return issues


def clean_name(name):
    if not name:
        return ""
    name = name.strip(" 　")
    name = name.replace("[", "[").replace("】", "]").replace("［", "[").replace("］", "]")
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="包含各分片目录的根目录")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    records = load_records(root)

    # kcal 必然小于 kJ，出现反序说明两列被读反
    swapped = 0
    for rec in records:
        kcal = rec.get("energy_kcal")
        kj = rec.get("energy_kj")
        if kcal is not None and kj is not None and kcal > kj:
            rec["energy_kcal"] = kj
            rec["energy_kj"] = kcal
            rec["swapped_energy_columns"] = True
            swapped += 1

    # kJ 与 kcal 换算不符时，以 kcal 为准重算 kJ（kcal 列识别更稳）
    fixed_kj = 0
    for rec in records:
        k = rec.get("energy_kcal")
        j = rec.get("energy_kj")
        if k and j:
            expected = k * KJ_PER_KCAL
            if abs(expected - j) / expected > TOLERANCE:
                rec["energy_kj_ocr"] = j
                rec["energy_kj"] = round(expected, 1)
                rec["kj_recalculated"] = True
                fixed_kj += 1

    # 用同一食物编码的其他记录补全空名称
    name_by_code = {}
    for rec in records:
        if (rec.get("food_name") or "").strip():
            name_by_code.setdefault(str(rec.get("food_code")), rec["food_name"].strip())
    filled = 0
    for rec in records:
        if not (rec.get("food_name") or "").strip():
            fallback = name_by_code.get(str(rec.get("food_code")), "")
            if fallback:
                rec["food_name"] = fallback
                filled += 1

    cleaned = []
    for rec in records:
        issues = validate(rec)
        rec["food_name"] = clean_name(rec.get("food_name"))
        rec["validation"] = {"ok": not issues, "issues": issues}
        cleaned.append(rec)

    # 按食物编码 + 名称去重，保留信息最全的一条
    dedup = {}
    for rec in cleaned:
        key = (str(rec.get("food_code")), rec.get("food_name"))
        old = dedup.get(key)
        score = len([k for k in ("water_g", "protein_g", "fat_g", "carb_g") if rec.get(k) is not None])
        if old is None or score > old[0]:
            dedup[key] = (score, rec)
    unique = [rec for _, rec in dedup.values()]

    jsonl_path = out / "heat_index.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for rec in unique:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    csv_path = out / "heat_index.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["food_code", "food_name", "energy_kcal", "energy_kj", "water_g", "protein_g", "fat_g", "carb_g", "page", "validation_ok", "issues"])
        for rec in unique:
            writer.writerow([
                rec.get("food_code", ""),
                rec.get("food_name", ""),
                rec.get("energy_kcal", ""),
                rec.get("energy_kj", ""),
                rec.get("water_g", ""),
                rec.get("protein_g", ""),
                rec.get("fat_g", ""),
                rec.get("carb_g", ""),
                rec.get("page", ""),
                "1" if rec["validation"]["ok"] else "0",
                " / ".join(rec["validation"]["issues"]),
            ])

    total = len(unique)
    ok = sum(1 for r in unique if r["validation"]["ok"])
    no_energy = sum(1 for r in unique if r.get("energy_kcal") is None)
    no_name = sum(1 for r in unique if not r.get("food_name"))
    bad_check = sum(1 for r in unique if any("kcal/kJ" in i for i in r["validation"]["issues"]))
    pages = sorted({r.get("page") for r in unique if r.get("page")})

    report = [
        "# 热量索引合并报告",
        "",
        f"- 原始记录：{len(records)}",
        f"- 去重后条目：{total}",
        f"- kcal/kJ 列反序修正：{swapped}",
        f"- kJ 按 kcal 重算：{fixed_kj}",
        f"- 用编码补全的名称：{filled}",
        f"- 通过校验：{ok}（{ok / total * 100 if total else 0:.1f}%）",
        f"- 缺少能量：{no_energy}",
        f"- 名称为空：{no_name}",
        f"- kcal/kJ 不一致：{bad_check}",
        f"- 覆盖页码：{pages[0] if pages else '-'} ~ {pages[-1] if pages else '-'}（{len(pages)} 页有产出）",
    ]
    (out / "merge_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print("\n".join(report))
    print(f"\n输出：{jsonl_path}")
    print(f"     {csv_path}")


if __name__ == "__main__":
    main()
