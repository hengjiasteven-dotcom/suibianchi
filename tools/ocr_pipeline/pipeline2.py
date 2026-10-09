#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""中国食物成分表扫描件 OCR 流水线原型 v2。

改进点：支持多级表头合并（第一版只抓到第二级表头，丢掉了能量/蛋白质等列）。
流程：渲染 -> 方向检测 -> 旋转校正 -> OCR -> 多级表头合并 -> 表格行列重建 -> 数值校验
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

TABLE_HINTS = (
    "食物编码",
    "食物名称",
    "能量",
    "蛋白质",
    "脂肪",
    "碳水化合物",
    "水分",
    "可食部",
)

CODE_RE = re.compile(r"^\d{5,7}$")
NUM_RE = re.compile(r"^\d+(\.\d+)?$")

ENERGY_TOL_RATIO = 0.25
ENERGY_TOL_ABS = 30.0


def render_page(pdf_path, page, dpi, out_png):
    out_png.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["POPPLER_DATADIR"] = str(POPPLER_SHARE)
    cmd = [
        str(PDFTOPPM),
        "-f",
        str(page),
        "-l",
        str(page),
        "-r",
        str(dpi),
        "-png",
        "-singlefile",
        str(pdf_path),
        str(out_png.with_suffix("")),
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
            items.append(
                {"box": [[float(x), float(y)] for x, y in box], "text": text, "score": float(score)}
            )
    return items


def detect_orientation(engine, img, scale=0.4):
    small = img.resize(
        (max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS
    )
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
        trials.append(
            {"angle": angle, "items": len(items), "mean": round(mean, 4), "score": round(score, 2)}
        )
        if best is None or score > best[0]:
            best = (score, angle)
    if best is None:
        return 0, trials
    return best[1], trials


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
        placed = False
        for row in rows:
            if abs(row["cy"] - cy) <= tol:
                row["items"].append(item)
                row["cy"] = sum(box_center(i["box"])[1] for i in row["items"]) / len(row["items"])
                placed = True
                break
        if not placed:
            rows.append({"cy": cy, "items": [item]})
    for row in rows:
        row["items"].sort(key=lambda i: box_center(i["box"])[0])
        row["text"] = "".join(i["text"] for i in row["items"])
    rows.sort(key=lambda r: r["cy"])
    return rows


def find_table_band(rows, max_lookback=6):
    """找数据起始行，以及其上方属于表头的若干行（支持多级表头）。"""
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
        if any(hint in text for hint in TABLE_HINTS) or re.search(r"(kcal|kJ|mg|μg|g)", text):
            band.append(row)
    return band, data_start


def build_columns(band_rows):
    """合并多级表头：按 x 区间重叠聚类，拼接同一列的上下层文字。"""
    items = [item for row in band_rows for item in row["items"]]
    clusters = []
    for item in sorted(items, key=lambda i: box_center(i["box"])[0]):
        x0, x1 = box_x_range(item["box"])
        placed = False
        for cluster in clusters:
            overlap = min(x1, cluster["x1"]) - max(x0, cluster["x0"])
            if overlap > 0.35 * min(x1 - x0, cluster["x1"] - cluster["x0"]):
                cluster["items"].append(item)
                cluster["x0"] = min(cluster["x0"], x0)
                cluster["x1"] = max(cluster["x1"], x1)
                placed = True
                break
        if not placed:
            clusters.append({"items": [item], "x0": x0, "x1": x1})
    columns = []
    for cluster in clusters:
        cluster["items"].sort(key=lambda i: box_center(i["box"])[1])
        name = "".join(i["text"] for i in cluster["items"])
        columns.append({"name": name, "x0": cluster["x0"], "x1": cluster["x1"]})
    columns.sort(key=lambda c: (c["x0"] + c["x1"]) / 2)
    return columns


def column_bounds(columns):
    centers = [(c["x0"] + c["x1"]) / 2 for c in columns]
    for idx, center in enumerate(centers):
        left = 0.0 if idx == 0 else (centers[idx - 1] + center) / 2
        right = float("inf") if idx == len(centers) - 1 else (center + centers[idx + 1]) / 2
        columns[idx]["left"] = left
        columns[idx]["right"] = right
    return columns


def assign_column(columns, x_center):
    for col in columns:
        if col["left"] <= x_center < col["right"]:
            return col
    return None


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


def extract_rows(rows, columns, data_start):
    foods = []
    for row in rows[data_start:]:
        items = row["items"]
        if not items:
            continue
        code_item = None
        for item in items:
            if CODE_RE.match(item["text"]):
                code_item = item
                break
        if code_item is None:
            continue

        nutrients = {}
        notes = []
        food_name_parts = []
        warnings = []
        code_center_x = box_center(code_item["box"])[0]

        for item in items:
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
            if cx < code_center_x:
                food_name_parts.append(item["text"])
                continue
            value, suspicious = normalize_number(item["text"])
            if value is None:
                warnings.append(f"数字解析失败：{item['text']}")
                continue
            if col["name"] not in nutrients:
                nutrients[col["name"]] = {
                    "value": value,
                    "raw": item["text"],
                    "score": round(item["score"], 3),
                }
            if suspicious:
                warnings.append(f"数字含可疑字符：{item['text']} -> {value}")

        foods.append(
            {
                "food_code": code_item["text"],
                "food_name": "".join(food_name_parts).strip(),
                "nutrients": nutrients,
                "notes": notes,
                "warnings": warnings,
            }
        )
    return foods


def pick_energy(nutrients):
    candidates = [(k, v) for k, v in nutrients.items() if "能量" in k]
    for key, value in candidates:
        if "kcal" in key.lower() or "千卡" in key:
            return key, value["value"]
    if candidates:
        return candidates[0]
    return None, None


def pick(nutrients, keyword, exclude=None):
    for key, value in nutrients.items():
        if keyword in key and (exclude is None or exclude not in key):
            return value["value"]
    return None


def validate_food(food):
    nutrients = food["nutrients"]
    issues = list(food["warnings"])
    _, energy = pick_energy(nutrients)
    protein = pick(nutrients, "蛋白质")
    fat = pick(nutrients, "脂肪")
    carb = pick(nutrients, "碳水化合物")
    water = pick(nutrients, "水分")
    ash = pick(nutrients, "灰分")

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
        total = water + protein + fat + carb + (ash or 0)
        if not 85 <= total <= 108:
            issues.append(f"成分合计异常：{total:.1f}")

    food["energy_kcal"] = energy
    food["validation"] = {"ok": not issues, "issues": issues}
    return food


def process_page(engine, pdf_path, page, dpi, work_dir, keep_images):
    png_path = work_dir / f"p{page:04d}.png"
    render_page(pdf_path, page, dpi, png_path)
    img = Image.open(png_path)
    angle, trials = detect_orientation(engine, img)
    rotated = img if angle == 0 else img.rotate(angle, expand=True)
    full_items = ocr_items(engine, np.array(rotated))

    rows = group_rows(full_items)
    band_rows, data_start = find_table_band(rows)
    columns = build_columns(band_rows) if band_rows else []
    column_bounds(columns)
    foods = extract_rows(rows, columns, data_start) if data_start is not None else []
    foods = [validate_food(f) for f in foods]

    page_warnings = []
    if not columns:
        page_warnings.append("未检测到表头，页面可能不是数据表或方向判断失败")
    elif not any("能量" in c["name"] for c in columns):
        page_warnings.append("未检测到能量列，可能是跨页表格的另一半")

    result = {
        "page": page,
        "rotation_deg": angle,
        "rotation_trials": trials,
        "header_rows": [row["text"] for row in band_rows],
        "header": [c["name"] for c in columns],
        "column_bounds": [
            {"name": c["name"], "x0": round(c["x0"], 1), "x1": round(c["x1"], 1)}
            for c in columns
        ],
        "foods": foods,
        "item_count": len(full_items),
        "page_warnings": page_warnings,
        "raw_items": [
            {
                "text": item["text"],
                "score": round(item["score"], 3),
                "center": [round(v, 1) for v in box_center(item["box"])],
            }
            for item in full_items
        ],
    }
    if not keep_images:
        png_path.unlink(missing_ok=True)
    return result


def parse_pages(spec):
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return pages


def write_report(out_dir, results, elapsed):
    total_foods = sum(len(r["foods"]) for r in results)
    ok_foods = sum(1 for r in results for f in r["foods"] if f["validation"]["ok"])
    lines = [
        "# 中国食物成分表 OCR 流水线报告",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 处理页数：{len(results)}",
        f"- 提取食物条目：{total_foods}",
        f"- 通过校验：{ok_foods}",
        f"- 校验通过率：{(ok_foods / total_foods * 100) if total_foods else 0:.1f}%",
        f"- 总耗时：{elapsed:.1f} 秒",
        "",
        "## 每页情况",
        "",
        "| 页码 | 校正角度 | 文本块 | 表头列 | 食物条目 | 通过校验 | 页面提示 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        ok = sum(1 for f in r["foods"] if f["validation"]["ok"])
        warn = "；".join(r.get("page_warnings", []))
        lines.append(
            f"| {r['page']} | {r['rotation_deg']} | {r['item_count']} | {len(r['header'])} | "
            f"{len(r['foods'])} | {ok} | {warn} |"
        )
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--pages", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--keep-images", action="store_true")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    out_dir = Path(args.out)
    work_dir = out_dir / "images"
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    engine = RapidOCR()
    results = []
    started = datetime.now()
    for page in parse_pages(args.pages):
        print(f"[page {page}] render + orientation ...", flush=True)
        result = process_page(engine, pdf_path, page, args.dpi, work_dir, args.keep_images)
        (pages_dir / f"page_{page:04d}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        ok = sum(1 for f in result["foods"] if f["validation"]["ok"])
        print(
            f"[page {page}] angle={result['rotation_deg']} items={result['item_count']} "
            f"foods={len(result['foods'])} ok={ok}",
            flush=True,
        )
        results.append(result)

    elapsed = (datetime.now() - started).total_seconds()
    (out_dir / "foods.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(out_dir, results, elapsed)
    print(f"done: {out_dir}")


if __name__ == "__main__":
    main()
