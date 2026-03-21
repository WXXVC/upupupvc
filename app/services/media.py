import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from app.models.config import load_config


VIDEO_CODEC_ARGS = {
    "h264": ("libx264", "aac"),
    "hevc": ("libx265", "aac"),
}
VIDEO_FORMATS = {"mp4", "mkv"}
IMAGE_FORMATS = {"jpg", "png", "webp"}


def ffmpeg_exe() -> Optional[str]:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def current_video_codec(override: str | None = None) -> str:
    codec = (override or load_config().transcode_video_codec or "h264").strip().lower()
    return codec if codec in VIDEO_CODEC_ARGS else "h264"


def current_video_format(override: str | None = None) -> str:
    fmt = (override or load_config().transcode_video_format or "mp4").strip().lower()
    return fmt if fmt in VIDEO_FORMATS else "mp4"


def current_image_format(override: str | None = None) -> str:
    fmt = (override or load_config().transcode_image_format or "jpg").strip().lower()
    return fmt if fmt in IMAGE_FORMATS else "jpg"


def current_video_suffix(override: str | None = None) -> str:
    return f".{current_video_format(override)}"


def current_image_suffix(override: str | None = None) -> str:
    return ".jpg" if current_image_format(override) == "jpg" else f".{current_image_format(override)}"


def ensure_faststart(input_path: Path) -> Path:
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        return input_path
    if input_path.suffix.lower() != ".mp4":
        return input_path
    output_path = input_path.with_name(f"{input_path.stem}.faststart{input_path.suffix}")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except Exception:
        return input_path


def reencode_to_mp4(input_path: Path, **kwargs) -> Path:
    return reencode_video(input_path, **kwargs)


def reencode_video(input_path: Path, *, video_codec: str | None = None, video_format: str | None = None) -> Path:
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        return input_path
    output_format = current_video_format(video_format)
    output_suffix = f".{output_format}"
    video_codec, audio_codec = VIDEO_CODEC_ARGS[current_video_codec(video_codec)]
    if input_path.suffix.lower() == output_suffix:
        output_path = input_path.with_name(f"{input_path.stem}.transcoded{output_suffix}")
    else:
        output_path = input_path.with_suffix(output_suffix)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        video_codec,
        "-c:a",
        audio_codec,
    ]
    if output_format == "mp4":
        cmd.extend(["-movflags", "+faststart"])
    cmd.append(str(output_path))
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except Exception:
        return input_path


def is_transcoded_video(input_path: Path) -> bool:
    return input_path.stem.endswith(".transcoded") and input_path.suffix.lower() in {".mp4", ".mkv"}


def convert_image_to_jpg(input_path: Path, **kwargs) -> Path:
    return convert_image(input_path, **kwargs)


def convert_image(input_path: Path, *, image_format: str | None = None) -> Path:
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        return input_path
    output_format = current_image_format(image_format)
    current_suffix = input_path.suffix.lower()
    if output_format == "jpg" and current_suffix in {".jpg", ".jpeg"}:
        return input_path
    if output_format != "jpg" and current_suffix == f".{output_format}":
        return input_path
    output_path = input_path.with_suffix(current_image_suffix(image_format))
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-frames:v",
        "1",
    ]
    if output_format == "jpg":
        cmd.extend(["-q:v", "2", "-pix_fmt", "yuvj420p"])
    elif output_format == "png":
        cmd.extend(["-compression_level", "2"])
    elif output_format == "webp":
        cmd.extend(["-c:v", "libwebp", "-q:v", "92"])
    cmd.append(str(output_path))
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except Exception:
        return input_path


def generate_thumbnail(input_path: Path, seconds: int = 3) -> Optional[Path]:
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        return None
    thumb_path = input_path.with_suffix(".jpg")
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        str(seconds),
        "-i",
        str(input_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(thumb_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return thumb_path
    except Exception:
        return None


def needs_reencode_for_streaming(input_path: Path, *, video_codec: str | None = None, video_format: str | None = None) -> bool:
    target_format = current_video_format(video_format)
    target_codec = current_video_codec(video_codec)
    suffix = input_path.suffix.lower()
    if target_format == "mp4" and suffix in {".ts", ".mkv", ".mov", ".avi", ".webm"}:
        return True
    if suffix not in {".mp4", ".m4v", ".mkv"}:
        return False
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        return False
    try:
        result = subprocess.run([ffmpeg, "-i", str(input_path)], capture_output=True, text=True)
        stderr = result.stderr or ""
        video_match = re.search(r"Video:\s*([^,\s]+)", stderr)
        audio_match = re.search(r"Audio:\s*([^,\s]+)", stderr)
        video_codec = (video_match.group(1).lower() if video_match else "")
        audio_codec = (audio_match.group(1).lower() if audio_match else "")
        expected_video = "hevc" if target_codec == "hevc" else "h264"
        if video_codec != expected_video:
            return True
        if audio_codec and audio_codec not in {"aac", "mp3"}:
            return True
        if suffix != f".{target_format}" and not (suffix == ".m4v" and target_format == "mp4"):
            return True
        return False
    except Exception:
        return False
