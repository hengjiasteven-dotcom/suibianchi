#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把导出的热量索引导入数据库。

用法（在 server 目录下）：
    python scripts/import_heat_index.py [索引 jsonl 路径]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.config import HEAT_INDEX_PATH  # noqa: E402


def import_index(path: Path = HEAT_INDEX_PATH) -> int:
    db.init_db()
    if not path.exists():
        print(f"索引文件不存在：{path}")
        return 0
    count = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            db.execute(
                "INSERT OR REPLACE INTO heat_index(food_code, food_name, energy_kcal, energy_kj, water_g, protein_g, fat_g, carb_g, search_keys) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    row["food_code"],
                    row["food_name"],
                    row["energy_kcal"],
                    row.get("energy_kj"),
                    row.get("water_g"),
                    row.get("protein_g"),
                    row.get("fat_g"),
                    row.get("carb_g"),
                    "",
                ),
            )
            count += 1
    print(f"导入 {count} 条热量数据 → {db.DB_PATH}")
    return count


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else HEAT_INDEX_PATH
    import_index(target)
