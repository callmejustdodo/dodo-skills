"""피그마에서 내보낸 PNG로 게시용 JPEG와 Slack 미리보기 한 장을 만든다.

    python prepare_deck.py <deck_dir>     # png/slide-*.png → slides/slide-*.jpg + preview.png

미리보기는 카드를 격자로 배치하고(7장 이상이면 4열, 그 이하는 3열) 남는 칸에
deck.json의 "preview" 정보(eyebrow, title 줄, lines, colors)를 요약 타일로 넣는다.
"""
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"  # macOS 기본 한글 폰트 (index 2=Regular, 4=Medium, 6=Bold)
BG = (31, 29, 27)


def font(size, idx):
    try:
        return ImageFont.truetype(FONT, size, index=idx)
    except OSError:
        return ImageFont.load_default(size)


def to_jpeg(deck_dir):
    pngs = sorted(glob.glob(os.path.join(deck_dir, "png", "slide-*.png")))
    if not pngs:
        sys.exit(f"{deck_dir}/png/slide-*.png 이 없어요")
    os.makedirs(os.path.join(deck_dir, "slides"), exist_ok=True)
    for old in glob.glob(os.path.join(deck_dir, "slides", "slide-*.jpg")):
        os.remove(old)
    images = []
    for p in pngs:
        im = Image.open(p).convert("RGB")
        out = os.path.join(deck_dir, "slides", os.path.basename(p)[:-4] + ".jpg")
        im.save(out, "JPEG", quality=92, optimize=True, subsampling=0)
        images.append(im)
        print(os.path.basename(out), im.size, os.path.getsize(out) // 1024, "KB")
    return images


def rounded_mask(size, r):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m


def build_preview(images, info, out_path):
    n = len(images)
    cols = 4 if n > 6 else 3
    rows = -(-(n + (1 if info else 0)) // cols)
    W = 540
    H = round(W * images[0].height / images[0].width)
    GAP, PAD = 36, 72
    CW, CH = PAD * 2 + cols * W + (cols - 1) * GAP, PAD * 2 + rows * H + (rows - 1) * GAP
    canvas = Image.new("RGB", (CW, CH), BG)
    cells = [(PAD + c * (W + GAP), PAD + r * (H + GAP)) for r in range(rows) for c in range(cols)]
    shadow = Image.new("L", (CW, CH), 0)
    sd = ImageDraw.Draw(shadow)
    for x, y in cells[:n]:
        sd.rounded_rectangle((x, y + 10, x + W, y + H + 10), 18, fill=150)
    canvas.paste(Image.new("RGB", (CW, CH), (8, 7, 6)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(18)))
    badge = font(22, 6)
    for k, (x, y) in enumerate(cells[:n]):
        thumb = images[k].resize((W, H), Image.LANCZOS)
        canvas.paste(thumb, (x, y), rounded_mask(thumb.size, 16))
        d = ImageDraw.Draw(canvas, "RGBA")
        label = f"{k + 1:02d}"
        tw = d.textlength(label, font=badge)
        d.rounded_rectangle((x + 14, y + 14, x + 36 + tw, y + 50), 18, fill=(20, 19, 18, 200))
        d.text((x + 25, y + 19), label, font=badge, fill=(255, 255, 255))
    if info and len(cells) > n:
        x, y = cells[n]
        d = ImageDraw.Draw(canvas)
        d.rounded_rectangle((x, y, x + W, y + H), 16, outline=(70, 66, 61), width=2)
        tx, yy = x + 44, y + 70
        if info.get("eyebrow"):
            d.text((tx, yy), info["eyebrow"], font=font(26, 4), fill=(230, 107, 37))
            yy += 48
        for line in info.get("title", []):
            d.text((tx, yy), line, font=font(54, 6), fill=(255, 255, 255))
            yy += 66
        yy += 40
        for line in info.get("lines", []):
            d.text((tx, yy), line, font=font(26, 2), fill=(196, 190, 182))
            yy += 44
        for i, c in enumerate(info.get("colors", [])):
            d.rectangle((tx + i * 40, y + H - 92, tx + i * 40 + 26, y + H - 66), fill=c)
    canvas.save(out_path, optimize=True)
    print("preview:", out_path, canvas.size, os.path.getsize(out_path) // 1024, "KB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    deck_dir = sys.argv[1]
    meta = json.load(open(os.path.join(deck_dir, "deck.json")))
    build_preview(to_jpeg(deck_dir), meta.get("preview"), os.path.join(deck_dir, "preview.png"))
