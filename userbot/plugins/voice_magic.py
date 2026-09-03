import asyncio
import io
import os
import subprocess
from pathlib import Path
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "audio"


@catub.cat_cmd(
    pattern="(vecho|vbass|vslow|vfast|vnightcore|vreverse|vrobot)(?:\\s|$)([\\s\\S]*)",
    command=("vecho", plugin_category),
    info={
        "header": "Apply voice changer & audio effects to any replied voice note or audio file.",
        "usage": "{tr}vecho, {tr}vbass, {tr}vslow, {tr}vfast, {tr}vnightcore, {tr}vreverse, {tr}vrobot (reply to voice/audio)",
    },
)
async def voice_effects(event):
    "Voice Changer & Audio Effects"
    cmd = event.pattern_match.group(1)
    reply = await event.get_reply_message()
    if not reply or not (reply.audio or reply.voice):
        return await edit_delete(event, "`Reply to a voice note or audio file to apply voice effects!`", 5)

    catevent = await edit_or_reply(event, f"`🎛️ Applying {cmd} effect with audio engine...`")
    download_dir = Path("temp_audio")
    download_dir.mkdir(exist_ok=True)
    input_file = await reply.download_media(file=str(download_dir / "input_audio"))
    output_file = str(download_dir / "output_audio.ogg")

    filter_map = {
        "vecho": "aecho=0.8:0.88:60:0.4",
        "vbass": "bass=g=15:f=110:w=0.6",
        "vslow": "atempo=0.7",
        "vfast": "atempo=1.5",
        "vnightcore": "asetrate=44100*1.3,aresample=44100,atempo=1.05",
        "vreverse": "areverse",
        "vrobot": "afftfilt=real='hypot(re,im)*sin(0)':imag='hypot(re,im)*cos(0)':win_size=512:overlap=0.75",
    }
    audio_filter = filter_map.get(cmd, "aecho=0.8:0.88:60:0.4")

    ffmpeg_cmd = [
        "ffmpeg", "-y", "-i", input_file,
        "-af", audio_filter,
        "-c:a", "libopus", "-b:a", "64k",
        output_file
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            return await catevent.edit("`Failed to process audio with ffmpeg!`")

        await catevent.edit("`📤 Uploading modulated voice note...`")
        await event.client.send_file(
            event.chat_id,
            output_file,
            voice_note=True,
            reply_to=reply.id,
            caption=f"🎙️ **Effect:** `{cmd.upper()}`",
        )
        await catevent.delete()
    except Exception as e:
        await catevent.edit(f"`Voice filter error: {e}`")
    finally:
        for f in download_dir.glob("*"):
            try:
                os.remove(f)
            except Exception:
                pass
