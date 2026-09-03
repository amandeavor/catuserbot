import asyncio
import io
import os
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "image"


@catub.cat_cmd(
    pattern="(blur|invert|grayscale|bw|pixelate|mirror|deepfry|spin)(?:\\s|$)([\\s\\S]*)",
    command=("blur", plugin_category),
    info={
        "header": "Apply visual transformations and meme effects to replied images or stickers.",
        "usage": "{tr}blur, {tr}invert, {tr}grayscale, {tr}pixelate, {tr}mirror, {tr}deepfry, {tr}spin",
    },
)
async def image_filters(event):
    "Photo & Meme Filters"
    cmd = event.pattern_match.group(1)
    args = event.pattern_match.group(2).strip()
    reply = await event.get_reply_message()
    if not reply or not (reply.photo or reply.sticker or reply.file):
        return await edit_delete(event, "`Reply to a photo or sticker to apply filters!`", 5)

    catevent = await edit_or_reply(event, f"`🎨 Processing {cmd} filter...`")
    download_dir = Path("temp_img")
    download_dir.mkdir(exist_ok=True)
    input_file = await reply.download_media(file=str(download_dir / "input_img"))

    try:
        im = Image.open(input_file).convert("RGBA")

        if cmd == "blur":
            radius = int(args) if args.isdigit() else 8
            res_img = im.filter(ImageFilter.GaussianBlur(radius))
            out_format = "PNG"
            out_file = str(download_dir / "blurred.png")
            res_img.save(out_file, out_format)

        elif cmd == "invert":
            # Invert RGB channels while preserving alpha
            r, g, b, a = im.split()
            rgb = Image.merge("RGB", (r, g, b))
            inv_rgb = ImageOps.invert(rgb)
            r2, g2, b2 = inv_rgb.split()
            res_img = Image.merge("RGBA", (r2, g2, b2, a))
            out_file = str(download_dir / "inverted.png")
            res_img.save(out_file, "PNG")

        elif cmd in ("grayscale", "bw"):
            res_img = ImageOps.grayscale(im.convert("RGB"))
            out_file = str(download_dir / "bw.jpg")
            res_img.save(out_file, "JPEG")

        elif cmd == "pixelate":
            pixel_size = int(args) if args.isdigit() else 16
            w, h = im.size
            small = im.resize((max(1, w // pixel_size), max(1, h // pixel_size)), Image.NEAREST)
            res_img = small.resize((w, h), Image.NEAREST)
            out_file = str(download_dir / "pixelated.png")
            res_img.save(out_file, "PNG")

        elif cmd == "mirror":
            w, h = im.size
            left = im.crop((0, 0, w // 2, h))
            right_mirrored = ImageOps.mirror(left)
            res_img = Image.new("RGBA", (w, h))
            res_img.paste(left, (0, 0))
            res_img.paste(right_mirrored, (w // 2, 0))
            out_file = str(download_dir / "mirrored.png")
            res_img.save(out_file, "PNG")

        elif cmd == "deepfry":
            rgb = im.convert("RGB")
            # Increase saturation
            sat = ImageEnhance.Color(rgb).enhance(3.5)
            # Increase contrast
            con = ImageEnhance.Contrast(sat).enhance(2.8)
            # Increase sharpness
            res_img = ImageEnhance.Sharpness(con).enhance(3.0)
            out_file = str(download_dir / "deepfried.jpg")
            res_img.save(out_file, "JPEG", quality=40)

        elif cmd == "spin":
            # Generate 360 degree spinning animated GIF
            frames = []
            for angle in range(0, 360, 15):
                rotated = im.rotate(-angle, resample=Image.BICUBIC, expand=False)
                frames.append(rotated)
            out_file = str(download_dir / "spinning.gif")
            frames[0].save(
                out_file,
                save_all=True,
                append_images=frames[1:],
                duration=40,
                loop=0,
                disposal=2,
            )

        await catevent.edit("`📤 Uploading edited image...`")
        await event.client.send_file(
            event.chat_id,
            out_file,
            caption=f"✨ **Filter:** `{cmd.upper()}`",
            reply_to=reply.id,
        )
        await catevent.delete()
    except Exception as e:
        await catevent.edit(f"`Image filter error: {e}`")
    finally:
        for f in download_dir.glob("*"):
            try:
                os.remove(f)
            except Exception:
                pass
