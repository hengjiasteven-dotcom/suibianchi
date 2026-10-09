#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""中国食物成分表扫描件 OCR 流水线原型。

流程：渲染 -> 方向检测 -> 旋转校正 -> OCR -> 表格行列重建 -> 数值校验
输出：每页 JSON、汇总 foods.json、report.md

依赖（系统 Python 3.9 已具备）：
  rapidocr_onnxruntime, onnxruntime, opencv-python, numpy, Pillow
渲染依赖 Poppler 的 pdftoppm。
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

# 能量校验允许的相对偏差（Atwater 系数为近似值）
ENERGY_TOL_RATIO = 0.25
ENERGY_TOL_ABS = 30.0


def render_page(pdf_path: Path, page: int, dpi: int, out_png: Path) -> Path:
    """用 pdftoppm 渲染单页为 PNG。out_png 需要包含 .png 后缀。"""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["POPPLER_DATADIR"] = str(POPPLER_SHARE)
    prefix = out_png.with_suffix("")
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
        str(prefix),
    ]
    subprocess.run(cmd, check=True, env=env, capture_output=True)
    if not out_png.exists():
        raise RuntimeError(f"渲染失败：{out_png}")
    return out_png


def ocr_items(engine: RapidOCR, image: np.ndarray):
    """返回 [{box, text, score}]。"""
    result, _ = engine(image)
    items = []
    for row in result or []:
        box, text, score = row[0], row[1], row[2]
        text = str(text).strip()
        if text:
            items.append({"box": [[float(x), float(y)] for x, y in box], "text": text, "score": float(score)})
    return items


def detect_orientation(engine: RapidOCR, img: Image.Image, scale: float = 0.4):
    """在缩小图上试跑四个方向，选置信度总量最高者。"""
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
    """按 y 中心把文本框聚成行。"""
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


def find_header_row(rows):
    """找包含食物编码/食物名称的表头行。"""
    for row in rows:
        text = row["text"]
        if "食物编码" in text or ("食物名称" in text and ("能量" in text or "水分" in text)):
            return row
    return None


def build_columns(header_row):
    columns = []
    for item in header_row["items"]:
        x0, x1 = box_x_range(item["box"])
        columns.append({"name": item["text"], "x0": x0, "x1": x1})
    columns.sort(key=lambda c: (c["x0"] + c["x1"]) / 2)
    return columns


def column_bounds(columns):
    """由表头列中心推出一组连续且不重叠的列边界。"""
    centers = [(c["x0"] + c["x1"]) / 2 for c in columns]
    bounds = []
    for idx, center in enumerate(centers):
        left = 0.0 if idx == 0 else (centers[idx - 1] + center) / 2
        right = float("inf") if idx == len(centers) - 1 else (center + centers[idx + 1]) / 2
        bounds.append((left, right))
    for col, (left, right) in zip(columns, bounds):
        col["left"] = left
        col["right"] = right
    return columns


def assign_column(columns, x_center):
    for col in columns:
        if col["left"] <= x_center < col["right"]:
            return col
    return None


def normalize_number(text):
    """清洗 OCR 数字，返回 (float|None, 是否可疑)。"""
    raw = text.strip()
    cleaned = raw.replace("，", ".").replace(",", ".").replace("·", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if not cleaned:
        return None, True
    if cleaned.count(".") > 1:
        return None, True
    if not NUM_RE.match(cleaned):
        return None, True
    try:
        value = float(cleaned)
    except ValueError:
        return None, True
    suspicious = raw != cleaned
    return value, suspicious


def extract_rows(rows, columns, header_index):
    """从表头下方抽取食物行。"""
    foods = []
    for row in rows[header_index + 1 :]:
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
            if "名称" in col["name"] or cx < code_center_x:
                food_name_parts.append(item["text"])
                continue
            value, suspicious = normalize_number(item["text"])
            if value is None:
                if item["text"] and not re.search(r"[，。；:：、]", item["text"]):
                    warnings.append(f"数字解析失败：{item['text']}")
                continue
            nutrients.setdefault(col["name"], {"value": value, "raw": item["text"], "score": round(item["score"], 3)})
            if suspicious:
                warnings.append(f"数字含可疑字符：{item['text']} -> {value}")
        foods.append(
            {
                "food_code": code_item["text"],
                "food_name": "".join(food_name_parts).strip(),
                "nutrients": nutrients,
                "warnings": warnings,
            }
        )
    return foods


def pick_energy(nutrients):
    """在营养素字典中找能量列（优先 kcal）。"""
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
    """能量与宏量营养素的一致性校验。"""
    nutrients = food["nutrients"]
    issues = list(food["warnings"])
    energy_key, energy = pick_energy(nutrients)
    protein = pick(nutrients, "蛋白质")
    fat = pick(nutrients, "脂肪")
    carb = pick(nutrients, "碳水化合物")
    water = pick(nutrients, "水分")
    ash = pick(nutrients, "灰分")

    if energy is None:
        issues.append("缺少能量值")
    elif not (0 <= energy <= 900):
        issues.append(f"能量超出合理范围：{energy}")

    macro_sum = None
    if None not in (protein, fat, carb):
        macro_sum = 4 * protein + 9 * fat + 4 * carb
    if energy is not None and macro_sum is not None:
        diff = abs(macro_sum - energy)
        tol = max(ENERGY_TOL_ABS, ENERGY_TOL_RATIO * energy)
        if diff > tol:
            issues.append(f"能量与宏量营养素不一致：标注 {energy}，按 4/9/4 估算 {macro_sum:.1f}")

    if None not in (water, protein, fat, carb):
        total = water + protein + fat + carb
        if ash is not None:
            total += ash
        if not (85 <= total <= 108):
            issues.append(f"成分合计异常：水+蛋白+脂肪+碳水(+灰分)={total:.1f}")

    food["energy_kcal"] = energy
    food["validation"] = {"ok": not issues, "issues": issues}
    return food


def process_page(engine, pdf_path, page, dpi, work_dir, keep_images):
    png_path = work_dir / f"{pdf_path.stem[:12]}_p{page:04d}.png"
    render_page(pdf_path, page, dpi, png_path)
    img = Image.open(png_path)
    angle, trials = detect_orientation(engine, img)
    rotated = img if angle == 0 else img.rotate(angle, expand=True)
    full_items = ocr_items(engine, np.array(rotated))
    rows = group_rows(full_items)
    header = find_header_row(rows)
    header_index = rows.index(header) if header else -1
    columns = build_columns(header) if header else []
    column_bounds(columns)
    foods = extract_rows(rows, columns, header_index) if header else []
    foods = [validate_food(f) for f in foods]
    result = {
        "page": page,
        "rotation_deg": angle,
        "rotation_trials": trials,
        "header": [c["name"] for c in columns],
        "foods": foods,
        "item_count": len(full_items),
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
        "| 页码 | 校正角度 | 文本块 | 表头列 | 食物条目 | 通过校验 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        ok = sum(1 for f in r["foods"] if f["validation"]["ok"])
        lines.append(
            f"| {r['page']} | {r['rotation_deg']} | {r['item_count']} | {len(r['header'])} | {len(r['foods'])} | {ok} |"
        )
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--pages", required=True, help="如 200 或 45-50,60")
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
        print(f"[page {page}] 渲染 + 方向检测 ...", flush=True)
        result = process_page(engine, pdf_path, page, args.dpi, work_dir, args.keep_images)
        (pages_dir / f"page_{page:04d}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        ok = sum(1 for f in result["foods"] if f["validation"]["ok"])
        print(
            f"[page {page}] 角度={result['rotation_deg']} 文本块={result['item_count']} "
            f"食物={len(result['foods'])} 通过={ok}",
            flush=True,
        )
        results.append(result)

    elapsed = (datetime.now() - started).total_seconds()
    (out_dir / "foods.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out_dir, results, elapsed)
    print(f"完成，输出目录：{out_dir}")


if __name__ == "__main__":
    main()
