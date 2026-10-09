#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""中国食物成分表扫描件 OCR 流水线原型 v3。

在 v2 基础上的两项关键修复：
1. 对开页合并：该书每张食物表横跨左右两页，左页放水分/能量/蛋白质/脂肪/碳水等，
   右页放维生素/矿物质，需按食物编码把两页结果合并。
2. 列边界重建：改用“最细表头行”作为列模板，避免跨列合并表头（如能量 kcal/kJ）
   被聚成一个巨宽列，导致数值错位。
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

POPPLER_BIN = Path(
    r"C:\Users\张恒嘉\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin"
)
POPPLER_SHARE = Path(
    r"C:\Users\张恒嘉\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\share\poppler"
)
PDFTOPPM = POPPLER_BIN / "pdftoppm.exe"

ROTATIONS = (0, 90, 180, 270)
TABLE_HINTS = ("食物编码", "食物名称", "能量", "蛋白质", "脂肪", "碳水化合物", "水分", "可食部")
CODE_RE = re.compile(r"^\d{5,7}$")
NUM_RE = re.compile(r"^\d+(\.\d+)?$")
ENERGY_TOL_RATIO = 0.25
ENERGY_TOL_ABS = 30.0


def render_page(pdf_path, page, dpi, out_png):
    out_png.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["POPPLER_DATADIR"] = str(POPPLER_SHARE)
    cmd = [
        str(PDFTOPPM), "-f", str(page), "-l", str(page), "-r", str(dpi),
        "-png", "-singlefile", str(pdf_path), str(out_png.with_suffix("")),
    ]
    subprocess.run(cmd, check=True, env=env, capture_output=True)
    if not out_png.exists():
        raise RuntimeError(f"渲染失败：{out_png}")
    return out_png


def ocr_items(engine, image):
    result, _ = engine(image)
    items = []
    for row in result or []:
        box, text, score = row[0], row[1], row[2]
        text = str(text).strip()
        if text:
            items.append({"box": [[float(x), float(y)] for x, y in box], "text": text, "score": float(score)})
    return items


def detect_orientation(engine, img, scale=0.4):
    small = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    best = None
    trials = []
    for angle in ROTATIONS:
        candidate = small if angle == 0 else small.rotate(angle, expand=True)
        items = ocr_items(engine, np.array(candidate))
        if not items:
            trials.append({"angle": angle, "items": 0, "mean": 0.0, "score": 0.0})
            continue
        scores = [i["score"] for i in items]
        mean = sum(scores) / len(scores)
        joined = "".join(i["text"] for i in items)
        hits = sum(1 for hint in TABLE_HINTS if hint in joined)
        score = sum(scores) * (1.0 + 0.05 * hits)
        if mean < 0.5:
            score *= 0.3
        trials.append({"angle": angle, "items": len(items), "mean": round(mean, 4), "score": round(score, 2)})
        if best is None or score > best[0]:
            best = (score, angle)
    return (best[1] if best else 0), trials


def box_center(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def box_height(box):
    ys = [p[1] for p in box]
    return max(ys) - min(ys)


def box_x_range(box):
    xs = [p[0] for p in box]
    return min(xs), max(xs)


def group_rows(items, tol_ratio=0.6):
    if not items:
        return []
    heights = sorted(box_height(i["box"]) for i in items)
    median_h = heights[len(heights) // 2]
    tol = max(8.0, median_h * tol_ratio)
    ordered = sorted(items, key=lambda i: box_center(i["box"])[1])
    rows = []
    for item in ordered:
        cy = box_center(item["box"])[1]
        for row in rows:
            if abs(row["cy"] - cy) <= tol:
                row["items"].append(item)
                row["cy"] = sum(box_center(i["box"])[1] for i in row["items"]) / len(row["items"])
                break
        else:
            rows.append({"cy": cy, "items": [item]})
    for row in rows:
        row["items"].sort(key=lambda i: box_center(i["box"])[0])
        row["text"] = "".join(i["text"] for i in row["items"])
    rows.sort(key=lambda r: r["cy"])
    return rows


def find_table_band(rows, max_lookback=6):
    data_start = None
    for idx, row in enumerate(rows):
        if any(CODE_RE.match(it["text"]) for it in row["items"]):
            data_start = idx
            break
    if data_start is None:
        return [], None
    band = []
    for row in rows[max(0, data_start - max_lookback) : data_start]:
        text = row["text"]
        if any(h in text for h in TABLE_HINTS) or re.search(r"(kcal|kJ|mg|μg|g|%)", text):
            band.append(row)
    return band, data_start


def build_columns(band_rows):
    """以条目最多的表头行为列模板，其余表头行按 x 邻近度并入，避免巨宽列。"""
    if not band_rows:
        return []
    base = max(band_rows, key=lambda r: len(r["items"]))
    cols = []
    for item in sorted(base["items"], key=lambda i: box_center(i["box"])[0]):
        x0, x1 = box_x_range(item["box"])
        cols.append({"parts": [item["text"]], "x0": x0, "x1": x1})
    for row in band_rows:
        if row is base:
            continue
        for item in row["items"]:
            cx, _ = box_center(item["box"])
            col = min(cols, key=lambda c: abs((c["x0"] + c["x1"]) / 2 - cx))
            if abs((col["x0"] + col["x1"]) / 2 - cx) <= max(30.0, (col["x1"] - col["x0"])):
                col["parts"].append(item["text"])
    for col in cols:
        col["name"] = "".join(col["parts"])
    cols.sort(key=lambda c: (c["x0"] + c["x1"]) / 2)
    return cols


def column_bounds(columns):
    centers = [(c["x0"] + c["x1"]) / 2 for c in columns]
    widths = [c["x1"] - c["x0"] for c in columns]
    median_w = sorted(widths)[len(widths) // 2] if widths else 50.0
    for idx, center in enumerate(centers):
        left = center - median_w / 2 if idx == 0 else (centers[idx - 1] + center) / 2
        right = center + median_w / 2 if idx == len(centers) - 1 else (center + centers[idx + 1]) / 2
        columns[idx]["left"] = left
        columns[idx]["right"] = right
    return columns


def assign_column(columns, x_center):
    """取最近列，并要求落在列中心的合理范围内。"""
    if not columns:
        return None
    best = min(columns, key=lambda c: abs((c["x0"] + c["x1"]) / 2 - x_center))
    center = (best["x0"] + best["x1"]) / 2
    limit = max(best["right"] - best["left"], 40.0)
    return best if abs(center - x_center) <= limit else None


def normalize_number(text):
    raw = text.strip()
    cleaned = raw.replace("，", ".").replace(",", ".").replace("·", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if not cleaned or cleaned.count(".") > 1 or not NUM_RE.match(cleaned):
        return None, True
    try:
        value = float(cleaned)
    except ValueError:
        return None, True
    return value, raw != cleaned


def extract_page(engine, pdf_path, page, dpi, work_dir, keep_images):
    png_path = work_dir / f"p{page:04d}.png"
    render_page(pdf_path, page, dpi, png_path)
    img = Image.open(png_path)
    angle, trials = detect_orientation(engine, img)
    rotated = img if angle == 0 else img.rotate(angle, expand=True)
    full_items = ocr_items(engine, np.array(rotated))
    rows = group_rows(full_items)
    band_rows, data_start = find_table_band(rows)
    columns = column_bounds(build_columns(band_rows)) if band_rows else []

    foods = []
    if data_start is not None:
        for row in rows[data_start:]:
            code_item = next((i for i in row["items"] if CODE_RE.match(i["text"])), None)
            if code_item is None:
                continue
            nutrients = {}
            food_name_parts = []
            notes = []
            warnings = []
            code_x = box_center(code_item["box"])[0]
            for item in row["items"]:
                if item is code_item:
                    continue
                cx, _ = box_center(item["box"])
                col = assign_column(columns, cx)
                if col is None:
                    continue
                if "名称" in col["name"]:
                    food_name_parts.append(item["text"])
                    continue
                if "备注" in col["name"]:
                    notes.append(item["text"])
                    continue
                if cx < code_x:
                    food_name_parts.append(item["text"])
                    continue
                value, suspicious = normalize_number(item["text"])
                if value is None:
                    warnings.append(f"数字解析失败：{item['text']}")
                    continue
                if col["name"] not in nutrients:
                    nutrients[col["name"]] = {"value": value, "raw": item["text"], "score": round(item["score"], 3)}
                if suspicious:
                    warnings.append(f"数字含可疑字符：{item['text']} -> {value}")
            foods.append({
                "food_code": code_item["text"],
                "food_name": "".join(food_name_parts).strip(),
                "nutrients": nutrients,
                "notes": notes,
                "warnings": warnings,
            })

    if not keep_images:
        png_path.unlink(missing_ok=True)
    return {
        "page": page,
        "rotation_deg": angle,
        "rotation_trials": trials,
        "header_rows": [r["text"] for r in band_rows],
        "header": [c["name"] for c in columns],
        "foods": foods,
        "item_count": len(full_items),
    }


def merge_pages(left, right):
    """按食物编码合并左右页。"""
    right_by_code = {f["food_code"]: f for f in right["foods"]}
    merged = []
    for food in left["foods"]:
        other = right_by_code.get(food["food_code"])
        nutrients = dict(food["nutrients"])
        warnings = list(food["warnings"])
        notes = list(food["notes"])
        if other:
            for key, value in other["nutrients"].items():
                nutrients.setdefault(key, value)
            warnings.extend(other["warnings"])
            notes.extend(other["notes"])
        merged.append({
            "food_code": food["food_code"],
            "food_name": food["food_name"] or (other or {}).get("food_name", ""),
            "nutrients": nutrients,
            "notes": notes,
            "warnings": warnings,
        })
    for food in right["foods"]:
        if not any(m["food_code"] == food["food_code"] for m in merged):
            merged.append(food)
    return merged


def pick(nutrients, keyword, exclude=None):
    for key, value in nutrients.items():
        if keyword in key and (exclude is None or exclude not in key):
            return value["value"]
    return None


def pick_energy(nutrients):
    """优先取 kcal 列；本书列名形如“能量EnergykcalkJ”，按惯例第一个数值为 kcal。"""
    candidates = [(k, v) for k, v in nutrients.items() if "能量" in k or "Energy" in k]
    for key, value in candidates:
        if "kcal" in key.lower():
            return key, value["value"]
    if candidates:
        return candidates[0]
    return None, None


def validate(food):
    nutrients = food["nutrients"]
    issues = [
        w for w in food["warnings"]
        if not any(k in w for k in ("Tr", "tr", "微量", "—", "－"))
    ]
    _, energy = pick_energy(nutrients)
    protein = pick(nutrients, "蛋白质") or pick(nutrients, "Protein")
    fat = pick(nutrients, "脂肪") or pick(nutrients, "Fat")
    carb = pick(nutrients, "碳水化合物") or pick(nutrients, "CHO")
    water = pick(nutrients, "水分") or pick(nutrients, "Water")

    if energy is None:
        issues.append("缺少能量值")
    elif not 0 <= energy <= 900:
        issues.append(f"能量超出合理范围：{energy}")

    if energy is not None and None not in (protein, fat, carb):
        estimate = 4 * protein + 9 * fat + 4 * carb
        tolerance = max(ENERGY_TOL_ABS, ENERGY_TOL_RATIO * energy)
        if abs(estimate - energy) > tolerance:
            issues.append(f"能量与宏量营养素不一致：标注 {energy}，估算 {estimate:.1f}")

    if None not in (water, protein, fat, carb):
        total = water + protein + fat + carb
        if not 60 <= total <= 108:
            issues.append(f"成分合计异常：{total:.1f}")

    food["energy_kcal"] = energy
    food["validation"] = {"ok": not issues, "issues": issues}
    return food


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--pair", required=True, help="左右页，如 199,200")
    parser.add_argument("--out", required=True)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--keep-images", action="store_true")
    args = parser.parse_args()

    left_page, right_page = [int(x) for x in args.pair.split(",")]
    pdf_path = Path(args.pdf)
    out_dir = Path(args.out)
    work_dir = out_dir / "images"
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = RapidOCR()
    started = datetime.now()
    left = extract_page(engine, pdf_path, left_page, args.dpi, work_dir, args.keep_images)
    right = extract_page(engine, pdf_path, right_page, args.dpi, work_dir, args.keep_images)
    merged = [validate(f) for f in merge_pages(left, right)]

    payload = {
        "pdf": str(pdf_path),
        "pages": [left_page, right_page],
        "left": {k: left[k] for k in ("page", "rotation_deg", "header", "item_count")},
        "right": {k: right[k] for k in ("page", "rotation_deg", "header", "item_count")},
        "foods": merged,
    }
    out_path = out_dir / f"pair_{left_page}_{right_page}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for f in merged if f["validation"]["ok"])
    print(f"pages {left_page}+{right_page}: foods={len(merged)} ok={ok} elapsed={(datetime.now()-started).total_seconds():.1f}s")
    print(f"output: {out_path}")


if __name__ == "__main__":
    main()
