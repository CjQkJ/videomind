"""Long-video segmentation planning."""
from typing import List, Tuple


def plan_segments(
    duration_sec: float,
    threshold: int = 15 * 60,
    seg: int = 12 * 60,
    overlap: int = 30,
) -> List[Tuple[float, float]]:
    """
    Return list of (start, end) seconds.
    Short videos (<= threshold) are a single span.
    Longer videos are split into `seg`-second windows with `overlap`.
    """
    duration = float(duration_sec or 0)
    if duration <= 0:
        return [(0.0, 0.0)]
    if duration <= threshold:
        return [(0.0, duration)]

    spans: List[Tuple[float, float]] = []
    start = 0.0
    step = max(float(seg - overlap), 1.0)
    safe_overlap = min(max(int(overlap), 0), max(int(seg) - 1, 0))
    while start < duration:
        end = min(duration, start + seg)
        if spans and abs(start - spans[-1][0]) < 1e-6 and abs(end - spans[-1][1]) < 1e-6:
            break
        spans.append((float(start), float(end)))
        if end >= duration:
            break
        next_start = end - safe_overlap
        if next_start <= start:
            next_start = start + step
        start = next_start
    return spans


def probe_duration_seconds(video_path: str) -> float:
    import subprocess

    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            stderr=subprocess.DEVNULL,
            timeout=60,
        ).decode().strip()
        return float(out)
    except Exception:
        return 0.0


def cut_segment(video_path: str, start: float, end: float, out_path: str) -> str:
    import subprocess

    # re-encode for accurate cuts when stream copy may fail on keyframes
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(start, 0)),
        "-to",
        str(max(end, start)),
        "-i",
        video_path,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        out_path,
    ]
    # timeout: subprocess.run kills ffmpeg on expiry and raises; the caller's
    # existence/size check turns that into a normal job failure
    try:
        subprocess.run(
            cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800
        )
    except subprocess.TimeoutExpired:
        pass
    return out_path
