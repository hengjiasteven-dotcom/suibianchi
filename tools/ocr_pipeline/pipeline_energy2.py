#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""中国食物成分表 热量索引提取流水线 v2（性能修正版）。

与 v1 的区别：
- 只用左侧裁剪区识别；若裁剪区表头里根本没有“能量/Energy”列，
  说明这页是表格的右半张（只有维生素/矿物质），直接跳过，不再整页重跑。
- 只有裁剪区确实存在能量列、却没抓到数值时，才回退整页 OCR。

这样可以把大约一半的无效页面开销直接省掉。
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

# 避免 pdftoppm 每次调用都弹出控制台窗口
CREATE_NO_WINDOW = 0x08000000

TABLE_HINTS = ("食物编码", "食物名称", "能量", "蛋白质", "脂肪", "碳水化合物", "水分", "可食部")
CODE_RE = re.compile(r"^\d{5,7}$")
NUM_RE = re.compile(r"^\d+(\.\d+)?$")
TRACE = {"tr", "微量", "—", "－", "-"}


def log(msg, log_file=None):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if log_file:
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def render_page(pdf_path, page, dpi, out_png):
    out_png.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["POPPLER_DATADIR"] = str(POPPLER_SHARE)
    cmd = [
        str(PDFTOPPM), "-f", str(page), "-l", str(page), "-r", str(dpi),
        "-png", "-singlefile", str(pdf_path), str(out_png.with_suffix("")),
    ]
    subprocess.run(cmd, check=True, env=env, capture_output=True, creationflags=CREATE_NO_WINDOW)
    return out_png if out_png.exists() else None


def ocr(engine, image):
    result, _ = engine(image)
    items = []
    for row in result or []:
        box, text, score = row[0], row[1], row[2]
        text = str(text).strip()
        if text:
            items.append({"box": [[float(x), float(y)] for x, y in box], "text": text, "score": float(score)})
    return items


def center(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def x_range(box):
    xs = [p[0] for p in box]
    return min(xs), max(xs)


def bheight(box):
    ys = [p[1] for p in box]
    return max(ys) - min(ys)


def pick_orientation(engine, img, scale=0.35):
    small = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    best = None
    for angle in (270, 0):
        cand = small if angle == 0 else small.rotate(angle, expand=True)
        items = ocr(engine, np.array(cand))
        if not items:
            continue
        scores = [i["score"] for i in items]
        joined = "".join(i["text"] for i in items)
        hits = sum(1 for h in TABLE_HINTS if h in joined)
        total = sum(scores) * (1.0 + 0.05 * hits)
        if hits > 0:
            return angle, hits
        if best is None or total > best[0]:
            best = (total, angle, hits)
    return (best[1], best[2]) if best else (0, 0)


def group_rows(items, tol_ratio=0.6):
    if not items:
        return []
    heights = sorted(bheight(i["box"]) for i in items)
    tol = max(8.0, heights[len(heights) // 2] * tol_ratio)
    rows = []
    for item in sorted(items, key=lambda i: center(i["box"])[1]):
        cy = center(item["box"])[1]
        for row in rows:
            if abs(row["cy"] - cy) <= tol:
                row["items"].append(item)
                row["cy"] = sum(center(i["box"])[1] for i in row["items"]) / len(row["items"])
                break
        else:
            rows.append({"cy": cy, "items": [item]})
    for row in rows:
        row["items"].sort(key=lambda i: center(i["box"])[0])
        row["text"] = "".join(i["text"] for i in row["items"])
    rows.sort(key=lambda r: r["cy"])
    return rows


def find_band(rows, lookback=6):
    start = None
    for idx, row in enumerate(rows):
        if any(CODE_RE.match(i["text"]) for i in row["items"]):
            start = idx
            break
    if start is None:
        return [], None
    band = []
    for row in rows[max(0, start - lookback) : start]:
        text = row["text"]
        if any(h in text for h in TABLE_HINTS) or re.search(r"(kcal|kJ|mg|g)", text):
            band.append(row)
    return band, start


def build_columns(band_rows):
    if not band_rows:
        return []
    base = max(band_rows, key=lambda r: len(r["items"]))
    cols = []
    for item in sorted(base["items"], key=lambda i: center(i["box"])[0]):
        x0, x1 = x_range(item["box"])
        cols.append({"parts": [item["text"]], "x0": x0, "x1": x1})
    for row in band_rows:
        if row is base:
            continue
        for item in row["items"]:
            cx, _ = center(item["box"])
            col = min(cols, key=lambda c: abs((c["x0"] + c["x1"]) / 2 - cx))
            if abs((col["x0"] + col["x1"]) / 2 - cx) <= max(30.0, col["x1"] - col["x0"]):
                col["parts"].append(item["text"])
    for col in cols:
        col["name"] = "".join(col["parts"])
    cols.sort(key=lambda c: (c["x0"] + c["x1"]) / 2)
    return cols


def nearest(cols, xc):
    if not cols:
        return None
    best = min(cols, key=lambda c: abs((c["x0"] + c["x1"]) / 2 - xc))
    return best if abs((best["x0"] + best["x1"]) / 2 - xc) <= max(best["x1"] - best["x0"], 40.0) else None


def parse_num(text):
    raw = text.strip()
    if raw.lower() in TRACE:
        return 0.0, True, True
    cleaned = re.sub(r"[^0-9.]", "", raw.replace("，", ".").replace(",", ".").replace("·", "."))
    if not cleaned or cleaned.count(".") > 1 or not NUM_RE.match(cleaned):
        return None, False, False
    try:
        return float(cleaned), raw != cleaned, False
    except ValueError:
        return None, False, False


def extract_foods(items, dpi):
    """返回 (foods, header_names)。"""
    rows = group_rows(items)
    band, start = find_band(rows)
    cols = build_columns(band)
    if start is None or not cols:
        return [], []
    foods = []
    for row in rows[start:]:
        code_item = next((i for i in row["items"] if CODE_RE.match(i["text"])), None)
        if code_item is None:
            continue
        nutrient_values = []
        name_parts = []
        code_x = center(code_item["box"])[0]
        for item in row["items"]:
            if item is code_item:
                continue
            cx, _ = center(item["box"])
            col = nearest(cols, cx)
            if col is None:
                continue
            if "名称" in col["name"] or cx < code_x:
                name_parts.append(item["text"])
                continue
            value, suspicious, trace = parse_num(item["text"])
            if value is None:
                continue
            nutrient_values.append((col, value, trace))
        foods.append(
            {
                "food_code": code_item["text"],
                "food_name": "".join(name_parts).strip(),
                "values": nutrient_values,
                "dpi": dpi,
            }
        )
    return foods, [c["name"] for c in cols]


def energy_of(food):
    kcal = kj = None
    others = {}
    for col, value, trace in food["values"]:
        name = col["name"]
        low = name.lower()
        if "能量" in name or "energy" in low:
            if kcal is None:
                kcal = value
            elif kj is None:
                kj = value
        elif "水分" in name or "water" in low:
            others.setdefault("water_g", value)
        elif "蛋白质" in name or "protein" in low:
            others.setdefault("protein_g", value)
        elif "脂肪" in name or "fat" in low:
            others.setdefault("fat_g", value)
        elif "碳水化合物" in name or "cho" in low:
            others.setdefault("carb_g", value)
    return kcal, kj, others


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--pages", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--crop", type=float, default=0.5)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    start, end = [int(x) for x in args.pages.split("-")]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "foods.jsonl"
    progress_path = out_dir / "progress.json"
    log_path = out_dir / "run.log"
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    done = set()
    if progress_path.exists():
        done = set(json.loads(progress_path.read_text(encoding="utf-8")).get("done", []))

    engine = RapidOCR(intra_op_num_threads=args.threads, inter_op_num_threads=1)
    log(f"start {args.tag} pages {start}-{end} dpi={args.dpi} done_before={len(done)}", log_path)

    def mark(page):
        done.add(page)
        progress_path.write_text(
            json.dumps({"done": sorted(done), "updated": datetime.now().isoformat()}, ensure_ascii=False),
            encoding="utf-8",
        )

    for page in range(start, end + 1):
        if page in done:
            continue
        png = img_dir / f"p{page:04d}.png"
        try:
            if not render_page(Path(args.pdf), page, args.dpi, png):
                log(f"page {page}: render failed", log_path)
                mark(page)
                continue
            img = Image.open(png)
            angle, hits = pick_orientation(engine, img)
            if hits == 0:
                mark(page)
                log(f"page {page}: no table hints, skipped", log_path)
                continue
            rotated = img if angle == 0 else img.rotate(angle, expand=True)
            target = rotated
            if args.crop > 0 and rotated.width > rotated.height:
                target = rotated.crop((0, 0, int(rotated.width * args.crop), rotated.height))
            items = ocr(engine, np.array(target))
            foods, headers = extract_foods(items, args.dpi)
            has_energy_col = any("能量" in h or "energy" in h.lower() for h in headers)
            if not has_energy_col:
                mark(page)
                log(f"page {page}: angle={angle} no energy column, skipped", log_path)
                continue
            if not any(energy_of(f)[0] is not None for f in foods):
                items_full = ocr(engine, np.array(rotated))
                foods_full, _ = extract_foods(items_full, args.dpi)
                if any(energy_of(f)[0] is not None for f in foods_full):
                    foods = foods_full
            written = 0
            with open(jsonl_path, "a", encoding="utf-8") as fh:
                for food in foods:
                    kcal, kj, others = energy_of(food)
                    if kcal is None:
                        continue
                    rec = {
                        "source": Path(args.pdf).name,
                        "page": page,
                        "rotation_deg": angle,
                        "food_code": food["food_code"],
                        "food_name": food["food_name"],
                        "energy_kcal": kcal,
                        "energy_kj": kj,
                    }
                    rec.update(others)
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    written += 1
            mark(page)
            log(f"page {page}: angle={angle} foods={len(foods)} with_energy={written}", log_path)
        except Exception as exc:  # noqa: BLE001
            log(f"page {page}: ERROR {exc!r}", log_path)
            mark(page)
        finally:
            try:
                png.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
    log(f"finished {args.tag} pages {start}-{end}", log_path)


if __name__ == "__main__":
    main()
