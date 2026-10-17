"""Async FFmpeg processor: 4K DASH stream merger, precision timestamp trimmer, and MP3 ID3 cover art embedder."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

from app.core.config import settings
from app.core.exceptions import FFmpegProcessError
from app.core.logger import get_logger

logger = get_logger(__name__)


class FFmpegService:
    """Async FFmpeg operations wrapper using non-blocking subprocesses."""

    def __init__(self) -> None:
        self.ffmpeg_bin = settings.FFMPEG_PATH
        self.ffprobe_bin = settings.FFPROBE_PATH

    async def check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg executable is operational."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.ffmpeg_bin,
                "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return proc.returncode == 0 and b"ffmpeg version" in stdout
        except (NotImplementedError, AttributeError):
            # Fallback for Windows event loops where create_subprocess_exec is not implemented
            try:
                import subprocess
                res = await asyncio.to_thread(
                    subprocess.run,
                    [self.ffmpeg_bin, "-version"],
                    capture_output=True,
                )
                return res.returncode == 0 and b"ffmpeg version" in res.stdout
            except Exception as fb_err:
                logger.warning(f"FFmpeg check fallback failed: {fb_err}")
                return False
        except Exception as e:
            logger.warning(f"FFmpeg check failed: {e}")
            return False

    async def _run_command(self, cmd: list[str], task_description: str) -> None:
        """Execute an async FFmpeg command and raise FFmpegProcessError on failure."""
        logger.debug(f"Running FFmpeg command ({task_description}): {' '.join(cmd)}")
        try:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
                returncode = process.returncode
            except (NotImplementedError, AttributeError):
                # Fallback for Windows event loops without subprocess support
                import subprocess
                sub_res = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                )
                stdout, stderr = sub_res.stdout, sub_res.stderr
                returncode = sub_res.returncode

            if returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                logger.error(f"FFmpeg {task_description} failed (code {returncode}): {err_msg}")
                raise FFmpegProcessError(
                    message=f"FFmpeg error during {task_description}: {err_msg[-300:]}",
                    details={"return_code": returncode, "error": err_msg},
                )
        except FileNotFoundError:
            raise FFmpegProcessError(
                message=f"FFmpeg executable not found at '{self.ffmpeg_bin}'. Please install FFmpeg.",
                details={"ffmpeg_bin": self.ffmpeg_bin},
            )

    async def merge_video_audio(self, video_path: Path, audio_path: Path, output_path: Path) -> Path:
        """Merge a separate 4K/2K/1080p DASH video stream with an audio stream.
        
        Uses fast stream copy without quality degradation.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0?",
            "-movflags", "+faststart",
            str(output_path),
        ]

        try:
            await self._run_command(cmd, "4K DASH Video+Audio Merge")
        except FFmpegProcessError:
            # Fallback: re-encode audio to AAC if copy fails
            logger.info("Retrying merge with standard re-encode...")
            fallback_cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                str(output_path),
            ]
            await self._run_command(fallback_cmd, "Fallback Merge")

        return output_path

    async def trim_media(
        self,
        input_path: Path,
        output_path: Path,
        start_time: float,
        end_time: float,
        extract_audio: bool = False,
        audio_format: str = "mp3",
    ) -> Path:
        """Perform precision timestamp trimming with keyframe accuracy."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = end_time - start_time
        if duration <= 0:
            raise FFmpegProcessError(
                message=f"Invalid trim range: start={start_time}s, end={end_time}s. Duration must be > 0."
            )

        if extract_audio:
            # Trim direct to audio
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", str(input_path),
                "-vn",
            ]
            if audio_format == "mp3":
                cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
            elif audio_format == "m4a":
                cmd.extend(["-c:a", "aac", "-b:a", "256k"])
            elif audio_format == "wav":
                cmd.extend(["-c:a", "pcm_s16le"])
            else:
                cmd.extend(["-c:a", "copy"])

            cmd.append(str(output_path))
            await self._run_command(cmd, f"Audio Trim to {audio_format}")
            return output_path

        # Video trim: attempt fast stream copy first
        copy_cmd = [
            self.ffmpeg_bin,
            "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", str(input_path),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(output_path),
        ]

        try:
            await self._run_command(copy_cmd, "Fast Stream Copy Trim")
        except FFmpegProcessError:
            # Fallback: keyframe-accurate re-encode
            logger.info("Fast trim failed; falling back to keyframe-accurate re-encode...")
            encode_cmd = [
                self.ffmpeg_bin,
                "-y",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", str(input_path),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(output_path),
            ]
            await self._run_command(encode_cmd, "Precision Re-encode Trim")

        return output_path

    async def convert_to_audio(
        self,
        input_path: Path,
        output_path: Path,
        audio_format: str = "mp3",
        bitrate: str = "320k",
    ) -> Path:
        """Extract and transcode audio to high-fidelity MP3, M4A, FLAC, or WAV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(input_path),
            "-vn",
        ]

        fmt = audio_format.lower()
        if fmt == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", bitrate])
        elif fmt == "m4a":
            cmd.extend(["-c:a", "aac", "-b:a", bitrate])
        elif fmt == "flac":
            cmd.extend(["-c:a", "flac"])
        elif fmt == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif fmt == "opus":
            cmd.extend(["-c:a", "libopus", "-b:a", bitrate])
        else:
            cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k"])

        cmd.append(str(output_path))
        await self._run_command(cmd, f"Audio Conversion to {fmt}")
        return output_path

    def embed_id3_metadata(
        self,
        audio_path: Path,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        cover_art_path: Optional[Path] = None,
    ) -> None:
        """Embed ID3v2 metadata and cover art into MP3 or M4A files using Mutagen."""
        if not audio_path.exists():
            logger.warning(f"Cannot embed ID3 tags: {audio_path} does not exist.")
            return

        suffix = audio_path.suffix.lower()

        if suffix == ".mp3":
            try:
                from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError  # type: ignore
                try:
                    tags = ID3(str(audio_path))
                except ID3NoHeaderError:
                    tags = ID3()

                if title:
                    tags.add(TIT2(encoding=3, text=title))
                if artist:
                    tags.add(TPE1(encoding=3, text=artist))
                if album:
                    tags.add(TALB(encoding=3, text=album))

                if cover_art_path and cover_art_path.exists():
                    mime_type = "image/jpeg" if cover_art_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
                    with open(cover_art_path, "rb") as art_file:
                        tags.add(
                            APIC(
                                encoding=3,
                                mime=mime_type,
                                type=3,  # Cover (front)
                                desc="Cover",
                                data=art_file.read(),
                            )
                        )
                tags.save(str(audio_path))
                logger.debug(f"Embedded MP3 ID3 tags for {audio_path.name}")
            except Exception as e:
                logger.warning(f"Failed to embed MP3 ID3 tags: {e}")

        elif suffix in [".m4a", ".mp4"]:
            try:
                from mutagen.mp4 import MP4, MP4Cover  # type: ignore
                mp4_tags = MP4(str(audio_path))
                if title:
                    mp4_tags["\xa9nam"] = title
                if artist:
                    mp4_tags["\xa9ART"] = artist
                if album:
                    mp4_tags["\xa9alb"] = album

                if cover_art_path and cover_art_path.exists():
                    image_format = (
                        MP4Cover.FORMAT_JPEG
                        if cover_art_path.suffix.lower() in [".jpg", ".jpeg"]
                        else MP4Cover.FORMAT_PNG
                    )
                    with open(cover_art_path, "rb") as art_file:
                        mp4_tags["covr"] = [MP4Cover(art_file.read(), imageformat=image_format)]
                mp4_tags.save()
                logger.debug(f"Embedded M4A tags for {audio_path.name}")
            except Exception as e:
                logger.warning(f"Failed to embed M4A tags: {e}")

    async def extract_thumbnail(self, video_path: Path, output_image_path: Path, timestamp: float = 1.0) -> Path:
        """Extract a high-resolution still frame from a video."""
        output_image_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(output_image_path),
        ]
        await self._run_command(cmd, "Frame Thumbnail Extraction")
        return output_image_path


# Singleton FFmpeg service instance
ffmpeg_service = FFmpegService()
