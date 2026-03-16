import re
import shutil
import subprocess
from pathlib import Path
from typing import List


def split_by_size(source: Path, threshold_bytes: int) -> List[Path]:
    size = source.stat().st_size
    if size <= threshold_bytes:
        return [source]

    if _is_video(source) and _has_ffmpeg():
        parts = _split_with_ffmpeg(source, threshold_bytes)
        if parts:
            return parts

    return _split_binary(source, threshold_bytes)


def _split_binary(source: Path, threshold_bytes: int) -> List[Path]:
    parts: List[Path] = []
    part_index = 1
    with open(source, "rb") as f:
        while True:
            chunk = f.read(threshold_bytes)
            if not chunk:
                break
            part_path = source.with_name(f"{source.stem}.part{part_index}{source.suffix}")
            with open(part_path, "wb") as out:
                out.write(chunk)
            parts.append(part_path)
            part_index += 1
    return parts


def _split_with_ffmpeg(source: Path, threshold_bytes: int) -> List[Path]:
    duration = _probe_duration(source)
    if not duration:
        return []
    bitrate = (source.stat().st_size * 8) / duration
    segment_time = max(1, int((threshold_bytes * 8) / bitrate))
    output_pattern = source.with_name(f"{source.stem}.part%03d{source.suffix}")
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return []
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-c",
        "copy",
        "-map",
        "0",
        "-f",
        "segment",
        "-segment_time",
        str(segment_time),
        "-reset_timestamps",
        "1",
        str(output_pattern),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    return sorted(source.parent.glob(f"{source.stem}.part*{source.suffix}"))


def _probe_duration(source: Path) -> float:
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 0.0
    cmd = [ffmpeg, "-i", str(source)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr or ""
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", output)
        if not match:
            return 0.0
        hours = float(match.group(1))
        minutes = float(match.group(2))
        seconds = float(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    except Exception:
        return 0.0


def _is_video(source: Path) -> bool:
    return source.suffix.lower() in {".mp4", ".mkv", ".mov", ".ts", ".m4v", ".avi"}


def _has_ffmpeg() -> bool:
    try:
        import imageio_ffmpeg
        return bool(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return False


def safe_delete(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def move_with_template(path: Path, template: str) -> Path:
    from datetime import datetime

    base = template.strip() or "./uploaded/{date}/{type}"
    date = datetime.now().strftime("%Y%m%d")
    file_type = path.suffix.lstrip(".") or "file"
    target_dir = Path(base.format(date=date, type=file_type))
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / path.name
    try:
        return Path(shutil.move(str(path), str(target_path)))
    except Exception:
        return path
