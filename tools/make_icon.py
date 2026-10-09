"""把一张"圆形插画 + 白底"的方图做成 Android 启动图标。

做法：
- 把纯白底抠成透明（插画内部没有纯白像素，抠掉不会伤到图案），
  这样图标四周就不会再有那圈白；
- 普通图标 / 圆形图标 = 抠好底、铺满画布的透明 PNG；
- 自适应图标 = 同一个透明图放到 108dp 画布的 82dp 区域（比系统蒙版 72dp 大），
  背景色取插画外缘平均色，万一露出一点点也不是白色。
"""

import math
import os

from PIL import Image

SRC = r"C:\Users\张恒嘉\Pictures\AI生成\img711d593475074619b5ec9f1b4b5d6faf.png"
RES = r"C:\codex-work\吃饭App\android\app\src\main\res"

DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}

# 白底抠除阈值：min(R,G,B) >= HIGH 判为背景，<= LOW 保留
HIGH = 247
LOW = 237

src = Image.open(SRC).convert("RGB")
w, h = src.size

# 1) 按"白度"生成透明通道，边缘做一点柔和过渡
alpha = Image.new("L", (w, h), 255)
src_px = src.load()
alpha_px = alpha.load()
for y in range(h):
    for x in range(w):
        m = min(src_px[x, y])
        if m >= HIGH:
            alpha_px[x, y] = 0
        elif m <= LOW:
            alpha_px[x, y] = 255
        else:
            alpha_px[x, y] = int((HIGH - m) * 255 / (HIGH - LOW))

art = src.convert("RGBA")
art.putalpha(alpha)

# 2) 裁到有效内容，别浪费画布
bbox = alpha.getbbox()
if bbox:
    art = art.crop(bbox)
print("抠底后内容尺寸:", art.size)

# 3) 背景色 = 不透明外缘一圈的平均色
edge = []
for i in range(72):
    angle = i * 2 * math.pi / 72
    x = int(art.width / 2 + (art.width / 2 - 4) * math.cos(angle))
    y = int(art.height / 2 + (art.height / 2 - 4) * math.sin(angle))
    p = art.getpixel((x, y))
    if p[3] > 200:
        edge.append(p)
avg = tuple(round(sum(c[k] for c in edge) / len(edge)) for k in range(3))
print("插画外缘平均色:", avg, "#%02X%02X%02X" % avg)

for name, scale in DENSITIES.items():
    folder = os.path.join(RES, f"mipmap-{name}")
    os.makedirs(folder, exist_ok=True)

    size = int(round(48 * scale))
    square = art.resize((size, size), Image.LANCZOS)
    square.save(os.path.join(folder, "ic_launcher.png"))
    square.save(os.path.join(folder, "ic_launcher_round.png"))

    fg_size = int(round(108 * scale))
    art_size = int(round(fg_size * 82 / 108))
    foreground = Image.new("RGBA", (fg_size, fg_size), (0, 0, 0, 0))
    big = art.resize((art_size, art_size), Image.LANCZOS)
    offset = (fg_size - art_size) // 2
    foreground.paste(big, (offset, offset))
    foreground.save(os.path.join(folder, "ic_launcher_foreground.png"))

print("生成完成")
