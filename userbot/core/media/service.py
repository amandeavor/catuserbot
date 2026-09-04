# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

LOGS = logging.getLogger("Aetheris.MediaService")


class MediaServiceV5:
    """
    Production media processing service for Aetheris V5.
    Executes FFmpeg operations via secure asynchronous subprocess vectors without shell interpolation.
    """

    def __init__(self):
        self.ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
        self.ffprobe_path = shutil.which("ffprobe") or "ffprobe"
        self.hardware_accel: Optional[str] = None
        self._hw_checked = False

    async def detect_hardware_acceleration(self) -> Optional[str]:
        """Detects available hardware acceleration encoders (CUDA/NVENC, QSV, VAAPI)."""
        if self._hw_checked:
            return self.hardware_accel

        self._hw_checked = True
        try:
            proc = await asyncio.create_subprocess_exec(
                self.ffmpeg_path,
                "-encoders",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            encoders_text = stdout.decode("utf-8", "replace")

            if "h264_nvenc" in encoders_text:
                self.hardware_accel = "cuda"
                LOGS.info("Hardware acceleration enabled: NVIDIA NVENC (CUDA)")
            elif "h264_qsv" in encoders_text:
                self.hardware_accel = "qsv"
                LOGS.info("Hardware acceleration enabled: Intel QuickSync (QSV)")
            elif "h264_vaapi" in encoders_text:
                self.hardware_accel = "vaapi"
                LOGS.info("Hardware acceleration enabled: VA-API")
            else:
                self.hardware_accel = None
                LOGS.info("Using standard CPU software encoders for FFmpeg")
        except Exception as e:
            LOGS.debug("FFmpeg hardware acceleration probe: %s", e)
            self.hardware_accel = None

        return self.hardware_accel

    async def run_ffmpeg(self, args: List[str]) -> Tuple[bool, str, str]:
        """
        Executes an FFmpeg command with safe argument vector isolation.
        Guarantees zero shell string interpolation.
        """
        cmd = [self.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error"] + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            out = stdout.decode("utf-8", "replace").strip()
            err = stderr.decode("utf-8", "replace").strip()
            return (proc.returncode == 0, out, err)
        except Exception as e:
            LOGS.error("FFmpeg execution error: %s", e)
            return (False, "", str(e))

    async def extract_audio(
        self,
        input_path: str,
        output_path: str,
        bitrate: str = "192k",
    ) -> bool:
        """Extract audio stream from video file."""
        args = ["-i", input_path, "-vn", "-acodec", "libmp3lame", "-b:a", bitrate, output_path]
        success, _, err = await self.run_ffmpeg(args)
        if not success:
            LOGS.warning("extract_audio failure: %s", err)
        return success

    async def generate_thumbnail(
        self,
        video_path: str,
        output_thumb: str,
        seek_time: str = "00:00:01",
    ) -> bool:
        """Extract a high-quality video frame for use as thumbnail."""
        args = ["-ss", seek_time, "-i", video_path, "-vframes", "1", "-q:v", "2", output_thumb]
        success, _, _ = await self.run_ffmpeg(args)
        return success

    async def compress_video(
        self,
        input_path: str,
        output_path: str,
        crf: int = 28,
        preset: str = "fast",
    ) -> bool:
        """Compress video with adaptive rate factor."""
        hw = await self.detect_hardware_acceleration()
        if hw == "cuda":
            args = ["-i", input_path, "-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(crf), "-c:a", "aac", output_path]
        else:
            args = ["-i", input_path, "-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-c:a", "aac", output_path]

        success, _, err = await self.run_ffmpeg(args)
        return success

    async def adjust_audio_tempo_pitch(
        self,
        input_path: str,
        output_path: str,
        tempo: float = 1.0,
        pitch_semitones: float = 0.0,
    ) -> bool:
        """Adjust audio tempo and pitch cleanly."""
        filter_str = f"atempo={tempo}"
        if pitch_semitones != 0.0:
            filter_str = f"asetrate=44100*2^({pitch_semitones}/12),atempo={tempo}/(2^({pitch_semitones}/12))"

        args = ["-i", input_path, "-filter:a", filter_str, "-vn", output_path]
        success, _, _ = await self.run_ffmpeg(args)
        return success

    async def create_video_note(
        self,
        input_video: str,
        output_note: str,
        dimension: int = 384,
    ) -> bool:
        """Convert any video into a square round video note suitable for Telegram."""
        filter_str = f"scale={dimension}:{dimension}:force_original_aspect_ratio=decrease,pad={dimension}:{dimension}:(ow-iw)/2:(oh-ih)/2"
        args = ["-i", input_video, "-vf", filter_str, "-c:v", "libx264", "-t", "60", "-c:a", "aac", output_note]
        success, _, _ = await self.run_ffmpeg(args)
        return success


media_service = MediaServiceV5()
