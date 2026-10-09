#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把打好的 release 包发到七牛，并更新 server/release.json。

用法（在项目根目录）：
    python tools/publish_apk.py --notes "这次改了什么"
    python tools/publish_apk.py --notes "..." --force     # 强制更新（客户端不能跳过）

需要环境里有 QINIU_ACCESS_KEY / QINIU_SECRET_KEY / QINIU_BUCKET，
以及一个已经打好的包：
    cd android && gradlew assembleRelease -PapiBaseUrl=https://api.xiaodaidai.site/
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRADLE = ROOT / "android" / "app" / "build.gradle.kts"
APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
RELEASE_JSON = ROOT / "server" / "release.json"


def read_version():
    text = GRADLE.read_text(encoding="utf-8")
    code = re.search(r"versionCode\s*=\s*(\d+)", text)
    name = re.search(r'versionName\s*=\s*"([^"]+)"', text)
    if not code or not name:
        raise SystemExit("读不到 versionCode / versionName，检查 android/app/build.gradle.kts")
    return int(code.group(1)), name.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes", default="", help="这次更新说明，会显示在客户端的更新弹窗里")
    parser.add_argument("--force", action="store_true", help="标记为强制更新")
    parser.add_argument("--apk", default=str(APK), help="APK 路径，默认用 release 产物")
    args = parser.parse_args()

    apk_path = Path(args.apk)
    if not apk_path.exists():
        raise SystemExit(f"找不到 APK：{apk_path}\n先跑：cd android && gradlew assembleRelease -PapiBaseUrl=...")

    code, name = read_version()
    object_key = f"app/suibianchi-{name}.apk"
    print(f"版本：{name}（versionCode={code}）")
    print(f"APK ：{apk_path}  {apk_path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"目标：{object_key}")

    ak = os.environ.get("QINIU_ACCESS_KEY", "")
    sk = os.environ.get("QINIU_SECRET_KEY", "")
    bucket = os.environ.get("QINIU_BUCKET", "")
    if not (ak and sk and bucket):
        raise SystemExit("缺 QINIU_ACCESS_KEY / QINIU_SECRET_KEY / QINIU_BUCKET")

    from qiniu import Auth, put_file

    auth = Auth(ak, sk)
    token = auth.upload_token(bucket, object_key, 3600)
    result, info = put_file(token, object_key, str(apk_path), version="v2")
    print(f"上传：status={info.status_code}")
    if info.status_code != 200 or not result:
        raise SystemExit(f"上传失败：{getattr(info, 'text_body', info)}")

    payload = {
        "version_code": code,
        "version_name": name,
        "object_key": object_key,
        "notes": args.notes or f"更新到 {name}",
        "force": bool(args.force),
    }
    RELEASE_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已写入 {RELEASE_JSON}")
    print("\n下一步：把 server/release.json 同步到服务器并重启 shiji-api，")
    print("客户端下次进 App 就会看到更新提示。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
