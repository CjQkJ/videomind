import os
import re
import glob
import json
import time
import base64
import shutil
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Callable

# Upstream OpenAI-compatible endpoint (set OPENAI_BASE_URL when deploying)
DEFAULT_API_URL = os.getenv("OPENAI_BASE_URL", "")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3.6-flash-high")

# native video via Antigravity Gemini route (see antigravity-gemini-video-usage.md)
ANTIGRAVITY_GENERATE_TMPL = "{base}/antigravity/v1beta/models/{model}:generateContent"
UNDERSTAND_MODE = os.getenv("UNDERSTAND_MODE", "native")  # native | frames | auto
NATIVE_MAX_VIDEO_BYTES = int(os.getenv("NATIVE_MAX_VIDEO_BYTES", str(20 * 1024 * 1024)))
MAX_FRAMES = int(os.getenv("MAX_FRAMES", "100"))
AI_TIMEOUT_SEC = int(os.getenv("AI_TIMEOUT_SEC", "300"))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "16384"))


def resolve_b23_short_link(url: str) -> str:
    """Expand b23.tv short links by reading redirect Location (no full page fetch)."""
    if not url or "b23.tv" not in url.lower():
        return url
    short = url.strip()
    m = re.search(r"https?://b23\.tv/[A-Za-z0-9]+", short)
    if m:
        short = m.group(0)

    class _CaptureRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            # Stop after first redirect; Location already has full bilibili URL + BVid
            raise urllib.error.HTTPError(newurl, code, msg, headers, fp)

    opener = urllib.request.build_opener(_CaptureRedirect)
    req = urllib.request.Request(
        short,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    try:
        opener.open(req, timeout=20)
    except urllib.error.HTTPError as e:
        # e.filename / full_url may be the redirect target
        loc = e.headers.get("Location") if e.headers else None
        target = loc or getattr(e, "filename", None) or str(e)
        if isinstance(target, bytes):
            target = target.decode("utf-8", "replace")
        bv = re.search(r"(BV[a-zA-Z0-9]+)", target or "")
        if bv:
            return f"https://www.bilibili.com/video/{bv.group(1)}"
        if target and "bilibili.com" in target:
            return target.split("#")[0]
        raise RuntimeError(f"无法解析 b23 短链: {short} -> {target}") from e
    except Exception as e:
        raise RuntimeError(f"解析 b23 短链失败: {short}: {e}") from e
    return short


def normalize_bilibili_url(raw: str) -> str:
    """Normalize share text / short links to a canonical bilibili watch URL with BVid."""
    if not raw:
        return raw
    text = raw.strip()
    m = re.search(r"(BV[a-zA-Z0-9]+)", text)
    if m:
        return f"https://www.bilibili.com/video/{m.group(1)}"
    m = re.search(r"https?://(?:www\.)?bilibili\.com/video/[^\s]+", text)
    if m:
        u = m.group(0).rstrip("?,，。.)）\"'")
        bv = re.search(r"(BV[a-zA-Z0-9]+)", u)
        if bv:
            return f"https://www.bilibili.com/video/{bv.group(1)}"
        return u
    m = re.search(r"https?://b23\.tv/[A-Za-z0-9]+", text)
    if m:
        return resolve_b23_short_link(m.group(0))
    # bare short code pasted somehow
    if re.fullmatch(r"[A-Za-z0-9]{6,12}", text) and not text.startswith("BV"):
        try:
            return resolve_b23_short_link(f"https://b23.tv/{text}")
        except Exception:
            pass
    return text


def clean_display_filename(path_or_name: str) -> str:
    name = os.path.basename(path_or_name or "本地视频")
    name = re.sub(r"^[0-9a-f]{32}_", "", name, flags=re.I)
    return name or "本地视频"


def _run_cmd(cmd: List[str], check: bool = True, timeout: int = 900) -> subprocess.CompletedProcess:
    # timeout prevents a hung ffmpeg from blocking the worker slot forever
    return subprocess.run(
        cmd, check=check, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout
    )


def process_video_input(
    input_type: str,
    source_val: str,
    work_dir: str,
    update_progress: Optional[Callable] = None,
) -> Dict[str, Any]:
    if update_progress:
        update_progress(stage="download", progress=10, message="正在解析元数据与下载视频流...")

    os.makedirs(work_dir, exist_ok=True)
    video_path = os.path.join(work_dir, "input_video.mp4")
    metadata: Dict[str, Any] = {
        "title": "未知视频",
        "uploader": "未知作者",
        "duration_sec": 0,
        "source_type": input_type,
        "source_url": "",
        "language": "zh-CN",
    }

    if input_type == "bilibili_url":
        source_url = normalize_bilibili_url(source_val)
        # Always prefer canonical BV URL for downstream download/fallback
        bv_early = re.search(r"(BV[a-zA-Z0-9]+)", source_url or "")
        if bv_early:
            source_url = f"https://www.bilibili.com/video/{bv_early.group(1)}"
        metadata["source_url"] = source_url
        print(f"[download] resolved bilibili url: {source_url}")
        if update_progress:
            update_progress(stage="download", progress=12, message=f"已解析链接: {source_url}")

        def bilibili_api_download(bvid: str):
            api_req = urllib.request.Request(
                f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"},
            )
            with urllib.request.urlopen(api_req, timeout=30) as resp:
                b_data = json.loads(resp.read().decode("utf-8")).get("data", {})
            metadata["title"] = b_data.get("title", "B站视频")
            metadata["uploader"] = b_data.get("owner", {}).get("name", "UP主")
            metadata["duration_sec"] = int(b_data.get("duration") or 0)
            metadata["source_url"] = f"https://www.bilibili.com/video/{bvid}"
            cid = b_data.get("cid")
            if not cid:
                raise RuntimeError("Bilibili API fallback failed: missing cid")

            play_req = urllib.request.Request(
                f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=64&type=mp4&platform=html5",
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"},
            )
            with urllib.request.urlopen(play_req, timeout=30) as resp:
                p_data = json.loads(resp.read().decode("utf-8")).get("data", {})
            durl = (p_data.get("durl") or [{}])[0].get("url")
            if not durl:
                raise RuntimeError("Bilibili API fallback failed: no play URL")

            header = "Referer: https://www.bilibili.com/\r\nUser-Agent: Mozilla/5.0\r\n"
            _run_cmd(
                ["ffmpeg", "-y", "-headers", header, "-i", durl, "-c", "copy", video_path],
                check=True,
                timeout=1800,
            )
            if not os.path.exists(video_path) or os.path.getsize(video_path) < 1024:
                raise RuntimeError("Bilibili fallback download produced empty file")

        import yt_dlp

        ydl_opts = {
            "outtmpl": video_path,
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
            "merge_output_format": "mp4",
            "quiet": True,
            "nocheckcertificate": True,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.bilibili.com/",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(source_url, download=True)
                metadata["title"] = info.get("title", "B站视频")
                metadata["uploader"] = info.get("uploader", "UP主")
                metadata["duration_sec"] = int(info.get("duration") or 0)
        except Exception as e:
            print(f"[!] yt-dlp failed ({e}), trying Bilibili API fallback...")
            bvid_m = re.search(r"(BV[a-zA-Z0-9]+)", source_url)
            if not bvid_m and "b23.tv" in (source_val or ""):
                # last chance: resolve short link again
                try:
                    source_url = resolve_b23_short_link(source_val)
                    bvid_m = re.search(r"(BV[a-zA-Z0-9]+)", source_url)
                except Exception as e2:
                    print(f"[!] b23 resolve also failed: {e2}")
            if not bvid_m:
                raise RuntimeError(
                    f"无法从链接提取 BV 号（短链需先解析）。原始: {source_val} 解析后: {source_url}。底层错误: {e}"
                ) from e
            bilibili_api_download(bvid_m.group(1))
    else:
        if not source_val or not os.path.exists(source_val):
            raise FileNotFoundError(f"上传文件不存在: {source_val}")
        shutil.copy2(source_val, video_path)
        metadata["title"] = clean_display_filename(source_val)
        metadata["source_url"] = "本地文件上传"
        try:
            probe = subprocess.check_output(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                stderr=subprocess.DEVNULL,
                timeout=60,
            ).decode().strip()
            metadata["duration_sec"] = int(float(probe))
        except Exception:
            metadata["duration_sec"] = 0

    if not os.path.exists(video_path) or os.path.getsize(video_path) < 1024:
        raise RuntimeError("视频文件无效或下载失败")

    metadata["local_video_path"] = video_path
    with open(os.path.join(work_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return metadata


def prepare_video_for_native(video_path: str, work_dir: str) -> str:
    """Compress/trim video if too large for inlineData (~20MB recommended)."""
    size = os.path.getsize(video_path)
    if size <= NATIVE_MAX_VIDEO_BYTES:
        return video_path

    out = os.path.join(work_dir, "native_input.mp4")
    # scale down + reencode to keep under limit
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", "scale='min(720,iw)':-2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        out,
    ]
    _run_cmd(cmd, check=False)
    if os.path.exists(out) and os.path.getsize(out) > 1024:
        # still too big? cap duration progressively
        if os.path.getsize(out) > NATIVE_MAX_VIDEO_BYTES:
            out2 = os.path.join(work_dir, "native_input_capped.mp4")
            _run_cmd(
                ["ffmpeg", "-y", "-i", out, "-t", "600", "-c", "copy", out2],
                check=False,
                timeout=300,
            )
            if os.path.exists(out2) and os.path.getsize(out2) > 1024:
                return out2
        return out
    return video_path


def sample_frames(frames: List[str], max_frames: int = MAX_FRAMES) -> List[str]:
    if len(frames) <= max_frames:
        return frames
    if max_frames <= 1:
        return frames[:1]
    idxs = [round(i * (len(frames) - 1) / (max_frames - 1)) for i in range(max_frames)]
    seen = set()
    out = []
    for i in idxs:
        if i not in seen:
            seen.add(i)
            out.append(frames[i])
    return out


def extract_keyframes(
    video_path: str,
    work_dir: str,
    update_progress: Optional[Callable] = None,
) -> List[str]:
    if update_progress:
        update_progress(stage="keyframes", progress=35, message="正在提取视觉关键帧...")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频不存在: {video_path}")

    frames_dir = os.path.join(work_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    for old in glob.glob(os.path.join(frames_dir, "*.jpg")):
        try:
            os.remove(old)
        except OSError:
            pass

    out_pattern = os.path.join(frames_dir, "frame_%03d.jpg")
    _run_cmd(
        ["ffmpeg", "-y", "-i", video_path, "-vf", "fps=1/2,scale=720:-1", out_pattern],
        check=False,
    )
    frames = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))
    if not frames:
        raise RuntimeError("关键帧提取失败：未生成任何帧（视频可能损坏）")
    return frames


def _strip_code_fence(text: str) -> str:
    clean = (text or "").strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.I)
        clean = re.sub(r"\s*```$", "", clean)
    return clean.strip()


def _extract_json_object(text: str) -> str:
    clean = _strip_code_fence(text)
    if not clean:
        raise ValueError("模型返回空内容")
    try:
        json.loads(clean)
        return clean
    except Exception:
        pass
    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end > start:
        candidate = clean[start : end + 1]
        json.loads(candidate)
        return candidate
    raise ValueError("无法从模型输出中提取 JSON 对象")


def _repair_truncated_json(text: str) -> Dict[str, Any]:
    clean = _strip_code_fence(text)
    start = clean.find("{")
    if start < 0:
        raise ValueError("无 JSON 起始符")
    clean = clean[start:]
    attempts = [clean]
    if clean.count('"') % 2 == 1:
        attempts.append(clean.rsplit('"', 1)[0])
    for base in list(attempts):
        b = re.sub(r",\s*$", "", base)
        open_curly = b.count("{") - b.count("}")
        open_square = b.count("[") - b.count("]")
        attempts.append(b + ("]" * max(open_square, 0)) + ("}" * max(open_curly, 0)))
        for suffix in ["", "}", "]}", "}}", '"]}', '"}]}']:
            attempts.append(base + suffix)

    last_err = None
    for cand in attempts:
        try:
            return json.loads(cand)
        except Exception as e:
            last_err = e
    raise ValueError(f"JSON 修复失败: {last_err}")


def _normalize_canonical(data: Any, metadata: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        data = {"summary": str(data)}

    def as_list(v):
        return v if isinstance(v, list) else ([] if v is None else [v])

    def norm_claim(c, idx):
        if isinstance(c, str):
            return {"id": f"cl_{idx:02d}", "text": c, "type": "insight", "importance": "中"}
        if isinstance(c, dict):
            return {
                "id": c.get("id") or f"cl_{idx:02d}",
                "text": c.get("text") or c.get("content") or c.get("claim") or str(c),
                "type": c.get("type") or "insight",
                "importance": c.get("importance") or "中",
            }
        return {"id": f"cl_{idx:02d}", "text": str(c), "type": "insight", "importance": "中"}

    def norm_method(m, idx):
        if isinstance(m, str):
            return {"id": f"m_{idx:02d}", "name": m, "description": m, "steps": []}
        if isinstance(m, dict):
            steps = m.get("steps") or []
            if isinstance(steps, str):
                steps = [steps]
            return {
                "id": m.get("id") or f"m_{idx:02d}",
                "name": m.get("name") or m.get("title") or f"方法 {idx}",
                "description": m.get("description") or m.get("desc") or "",
                "steps": [str(s) for s in steps],
            }
        return {"id": f"m_{idx:02d}", "name": str(m), "description": str(m), "steps": []}

    def norm_chapter(ch, idx):
        if isinstance(ch, str):
            return {"id": f"ch_{idx:02d}", "title": ch, "start_time": "", "end_time": "", "summary": ch}
        if isinstance(ch, dict):
            return {
                "id": ch.get("id") or f"ch_{idx:02d}",
                "title": ch.get("title") or f"章节 {idx}",
                "start_time": ch.get("start_time") or "",
                "end_time": ch.get("end_time") or "",
                "summary": ch.get("summary") or ch.get("desc") or "",
            }
        return {"id": f"ch_{idx:02d}", "title": str(ch), "start_time": "", "end_time": "", "summary": str(ch)}

    def norm_example(ex, idx):
        if isinstance(ex, str):
            return {"id": f"ex_{idx:02d}", "title": f"示例 {idx}", "description": ex}
        if isinstance(ex, dict):
            return {
                "id": ex.get("id") or f"ex_{idx:02d}",
                "title": ex.get("title") or f"示例 {idx}",
                "description": ex.get("description") or ex.get("desc") or str(ex),
            }
        return {"id": f"ex_{idx:02d}", "title": f"示例 {idx}", "description": str(ex)}

    def norm_action(a, idx):
        if isinstance(a, str):
            return {"id": f"ac_{idx:02d}", "item": a, "priority": "中"}
        if isinstance(a, dict):
            return {
                "id": a.get("id") or f"ac_{idx:02d}",
                "item": a.get("item") or a.get("text") or a.get("action") or str(a),
                "priority": a.get("priority") or "中",
            }
        return {"id": f"ac_{idx:02d}", "item": str(a), "priority": "中"}

    def norm_evidence(ev, idx):
        if isinstance(ev, str):
            return {"id": f"ev_{idx:02d}", "timestamp": "", "quote_or_visual_clue": ev}
        if isinstance(ev, dict):
            return {
                "id": ev.get("id") or f"ev_{idx:02d}",
                "timestamp": ev.get("timestamp") or ev.get("time") or "",
                "quote_or_visual_clue": (
                    ev.get("quote_or_visual_clue")
                    or ev.get("quote")
                    or ev.get("clue")
                    or ev.get("text")
                    or str(ev)
                ),
            }
        return {"id": f"ev_{idx:02d}", "timestamp": "", "quote_or_visual_clue": str(ev)}

    return {
        "summary": str(data.get("summary") or ""),
        "chapters": [norm_chapter(x, i + 1) for i, x in enumerate(as_list(data.get("chapters")))],
        "claims": [norm_claim(x, i + 1) for i, x in enumerate(as_list(data.get("claims")))],
        "methods": [norm_method(x, i + 1) for i, x in enumerate(as_list(data.get("methods")))],
        "examples": [norm_example(x, i + 1) for i, x in enumerate(as_list(data.get("examples")))],
        "actions": [norm_action(x, i + 1) for i, x in enumerate(as_list(data.get("actions")))],
        "evidence": [norm_evidence(x, i + 1) for i, x in enumerate(as_list(data.get("evidence")))],
        "source": {
            "title": metadata.get("title"),
            "uploader": metadata.get("uploader"),
            "duration_sec": metadata.get("duration_sec"),
            "source_url": metadata.get("source_url"),
            "language": metadata.get("language") or "zh-CN",
        },
        "native_transcript": data.get("native_transcript") or "",
        "understand_mode": data.get("understand_mode") or "",
    }


def _http_json(url: str, payload: Dict[str, Any], api_key: str, timeout: int) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    return json.loads(raw)


def _extract_generate_content_text(res: Dict[str, Any]) -> str:
    texts = []
    for cand in res.get("candidates") or []:
        content = cand.get("content") or {}
        for part in content.get("parts") or []:
            t = part.get("text")
            if isinstance(t, str) and t.strip():
                texts.append(t)
    return "".join(texts).strip()


def antigravity_native_video_understand(
    video_path: str,
    metadata: Dict[str, Any],
    api_url: str,
    api_key: str,
    model_name: str,
    update_progress: Optional[Callable] = None,
    work_dir: Optional[str] = None,
) -> str:
    """
    Stage A: native video understanding via Antigravity Gemini route.
    POST {base}/antigravity/v1beta/models/{model}:generateContent
    with inlineData mimeType=video/mp4 + bare base64.
    """
    if update_progress:
        update_progress(stage="ai_extraction", progress=40, message="Gemini 原生视频理解中（inlineData）...")

    if work_dir:
        os.makedirs(work_dir, exist_ok=True)

    base = (api_url or DEFAULT_API_URL).rstrip("/")
    model = model_name or DEFAULT_MODEL
    endpoint = ANTIGRAVITY_GENERATE_TMPL.format(base=base, model=model)

    use_path = video_path
    if work_dir:
        use_path = prepare_video_for_native(video_path, work_dir)

    raw_bytes = open(use_path, "rb").read()
    if len(raw_bytes) > 80 * 1024 * 1024:
        raise RuntimeError(f"视频过大无法 inlineData（{round(len(raw_bytes)/1024/1024,1)}MB）")

    b64 = base64.b64encode(raw_bytes).decode("ascii")
    prompt = (
        f"视频标题：{metadata.get('title')}\n"
        f"UP主：{metadata.get('uploader')}\n"
        f"时长：{metadata.get('duration_sec')} 秒\n\n"
        "请完整观看这段视频，输出「原生内容复述」，要求：\n"
        "1. 按时间线（MM:SS）分段描述发生了什么\n"
        "2. 尽量保留原话/字幕要点\n"
        "3. 说明画面、操作步骤、可见文字、代码或图表\n"
        "4. 最后给 200-500 字总体主旨\n"
        "5. 不确定的信息标注「不确定」\n"
        "先只要详尽复述，不要输出 JSON，不要做成卡片模板。"
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "video/mp4",
                            "data": b64,
                        }
                    },
                    {"text": prompt},
                ],
            }
        ]
    }

    last_err = None
    for attempt in range(1, AI_MAX_RETRIES + 1):
        if update_progress:
            update_progress(
                stage="ai_extraction",
                progress=35 + attempt * 8,
                message=f"原生视频理解中（第 {attempt}/{AI_MAX_RETRIES} 次）...",
            )
        try:
            res = _http_json(endpoint, payload, api_key, timeout=AI_TIMEOUT_SEC)
            text = _extract_generate_content_text(res)
            if work_dir:
                with open(os.path.join(work_dir, "native_raw_response.json"), "w", encoding="utf-8") as f:
                    json.dump(res, f, ensure_ascii=False, indent=2)
                with open(os.path.join(work_dir, "native_transcript.md"), "w", encoding="utf-8") as f:
                    f.write(text or "")
            if not text:
                raise ValueError(f"原生理解返回空文本: {json.dumps(res, ensure_ascii=False)[:500]}")
            return text
        except Exception as e:
            last_err = e
            print(f"[!] native understand attempt {attempt} failed: {e}")
            time.sleep(min(2 * attempt, 6))
    raise RuntimeError(f"原生视频理解失败: {last_err}")


def structure_from_transcript(
    transcript: str,
    metadata: Dict[str, Any],
    api_url: str,
    api_key: str,
    model_name: str,
    update_progress: Optional[Callable] = None,
    work_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Stage B: pure-text structuring from native transcript."""
    if work_dir:
        os.makedirs(work_dir, exist_ok=True)
    if update_progress:
        update_progress(stage="ai_extraction", progress=75, message="基于原生复述做结构化提炼...")

    base = (api_url or DEFAULT_API_URL).rstrip("/")
    model = model_name or DEFAULT_MODEL
    endpoint = ANTIGRAVITY_GENERATE_TMPL.format(base=base, model=model)

    system_rules = """你是顶级知识结构化专家。下面输入是「视频原生复述文本」。你的任务是把它提炼成结构化 JSON。
严格只输出合法 JSON（不要 markdown 代码块、不要注释）。

Schema：
{
  "summary": "300-500字主旨",
  "chapters": [{"id":"ch_01","title":"简明小标题","start_time":"MM:SS","end_time":"MM:SS","summary":"80-150字章节摘要"}],
  "claims": [{"id":"cl_01","text":"完整观点陈述（一句话说清）","type":"insight|opinion|fact|warning","importance":"高|中|低"}],
  "methods": [{"id":"m_01","name":"方法/技巧名称","description":"解决什么问题、适用场景","steps":["动词开头可执行步骤1","步骤2"]}],
  "examples": [{"id":"ex_01","title":"案例标题","description":"背景+做法+结果的具体描述"}],
  "actions": [{"id":"ac_01","item":"看完就能做的具体行动","priority":"高|中|低"}],
  "evidence": [{"id":"ev_01","timestamp":"MM:SS","quote_or_visual_clue":"引用复述原话或描述具体画面"}]
}

质量要求（务必遵守）：
1. 【重点优先】claims 必须按 importance 降序排列（高→中→低）；最核心的观点 importance 设为"高"并放在最前。
2. 【信息密度】summary 第一句点明视频核心价值，随后展开 2-4 个主要论点；禁止"本视频介绍了…"这类空泛开头。
3. 【可执行】methods.steps 必须是动词开头、能照着做的具体操作；禁止"注意细节"这类笼统话。
4. 【可追溯】evidence 要引用复述中的原话或具体画面，作为观点的时间线锚点，尽量多给。
5. 【内容丰富】每个数组字段至少给 3 条（视频内容支持的话）；宁可详实，不要敷衍。
6. 【按类型侧重】操作/教程类视频多写 methods 和 steps；知识/观点类多写 claims；案例拆解类多写 examples。
7. 【标题精炼】chapters.title 和 methods.name 用简明短句，不要长段落。"""

    user_text = (
        f"视频标题：{metadata.get('title')}\n"
        f"UP主：{metadata.get('uploader')}\n"
        f"时长：{metadata.get('duration_sec')}秒\n\n"
        f"===== 原生复述 =====\n{transcript}\n===== END =====\n\n"
        "请输出完整 JSON。"
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": system_rules + "\n\n" + user_text}
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": AI_MAX_TOKENS,
            "temperature": 0.2,
        },
    }

    last_err = None
    for attempt in range(1, AI_MAX_RETRIES + 1):
        try:
            res = _http_json(endpoint, payload, api_key, timeout=AI_TIMEOUT_SEC)
            raw_text = _extract_generate_content_text(res)
            if work_dir:
                with open(os.path.join(work_dir, "structure_raw_response.json"), "w", encoding="utf-8") as f:
                    json.dump(res, f, ensure_ascii=False, indent=2)
            if not raw_text:
                raise ValueError("结构化返回空文本")
            try:
                parsed = json.loads(_extract_json_object(raw_text))
            except Exception:
                parsed = _repair_truncated_json(raw_text)
            parsed["native_transcript"] = transcript
            parsed["understand_mode"] = "native"
            return _normalize_canonical(parsed, metadata)
        except Exception as e:
            last_err = e
            print(f"[!] structure attempt {attempt} failed: {e}")
            time.sleep(min(2 * attempt, 6))
    raise RuntimeError(f"二次结构化失败: {last_err}")


def generate_canonical_json_from_frames(
    frames: List[str],
    metadata: Dict[str, Any],
    api_url: str,
    api_key: str,
    model_name: str,
    update_progress: Optional[Callable] = None,
    work_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Fallback Stage A+B combined: frames as image_url via OpenAI-compatible chat."""
    if update_progress:
        update_progress(stage="ai_extraction", progress=65, message="抽帧模式：多模态提炼中...")

    endpoint = (api_url or DEFAULT_API_URL).rstrip("/")
    if not endpoint.endswith("/v1/chat/completions"):
        if endpoint.endswith("/v1"):
            endpoint += "/chat/completions"
        else:
            endpoint += "/v1/chat/completions"

    system_prompt = """你是顶级视频内容分析专家。输入是按时间顺序的关键帧。
只输出合法 JSON 对象，字段含 summary/chapters/claims/methods/examples/actions/evidence。
数组元素必须是对象。summary 200-500字。"""

    frame_budgets = [
        sample_frames(frames, MAX_FRAMES),
        sample_frames(frames, min(60, MAX_FRAMES)),
        sample_frames(frames, min(36, MAX_FRAMES)),
    ]
    last_error = None
    raw_dump_path = os.path.join(work_dir, "ai_raw_response.txt") if work_dir else None

    for attempt, selected in enumerate(frame_budgets[:AI_MAX_RETRIES], start=1):
        if update_progress:
            update_progress(
                stage="ai_extraction",
                progress=60 + attempt * 5,
                message=f"抽帧提炼中（第 {attempt}/{AI_MAX_RETRIES} 次，{len(selected)} 帧）...",
            )
        content_parts: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"视频标题：{metadata.get('title')}\n"
                    f"UP主：{metadata.get('uploader')}\n"
                    f"时长：{metadata.get('duration_sec')}秒\n"
                    f"关键帧数：{len(selected)}\n请输出完整合法 JSON。"
                ),
            }
        ]
        for img_path in selected:
            with open(img_path, "rb") as f:
                b64_str = base64.b64encode(f.read()).decode("utf-8")
            content_parts.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"}}
            )

        payload = {
            "model": model_name or DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_parts},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": AI_MAX_TOKENS,
            "temperature": 0.2,
        }
        try:
            res = _http_json(endpoint, payload, api_key, timeout=AI_TIMEOUT_SEC)
            raw_text = (
                ((res.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            )
            if raw_dump_path:
                with open(raw_dump_path, "w", encoding="utf-8") as f:
                    f.write(raw_text if isinstance(raw_text, str) else json.dumps(raw_text, ensure_ascii=False))
            if not raw_text or not str(raw_text).strip():
                raise ValueError("模型返回空 content")
            try:
                parsed = json.loads(_extract_json_object(str(raw_text)))
            except Exception:
                parsed = _repair_truncated_json(str(raw_text))
            parsed["understand_mode"] = "frames"
            return _normalize_canonical(parsed, metadata)
        except Exception as e:
            last_error = e
            print(f"[!] frames AI attempt {attempt} failed: {e}")
            time.sleep(min(2 * attempt, 6))
    raise RuntimeError(f"抽帧 AI 提炼失败: {last_error}")


def generate_canonical_json(
    frames: List[str],
    metadata: Dict[str, Any],
    api_url: str,
    api_key: str,
    model_name: str,
    update_progress: Optional[Callable] = None,
    work_dir: Optional[str] = None,
    understand_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main extraction entry.
    Preferred: native video understand (Antigravity inlineData) -> structure JSON.
    Fallback: keyframe image_url path.
    """
    mode = (understand_mode or UNDERSTAND_MODE or "native").lower()
    video_path = metadata.get("local_video_path")

    def run_native() -> Dict[str, Any]:
        if not video_path or not os.path.exists(video_path):
            raise FileNotFoundError("缺少本地视频，无法原生理解")
        transcript = antigravity_native_video_understand(
            video_path=video_path,
            metadata=metadata,
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            update_progress=update_progress,
            work_dir=work_dir,
        )
        return structure_from_transcript(
            transcript=transcript,
            metadata=metadata,
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            update_progress=update_progress,
            work_dir=work_dir,
        )

    def run_frames() -> Dict[str, Any]:
        use_frames = frames
        if (not use_frames) and video_path and work_dir:
            use_frames = extract_keyframes(video_path, work_dir, update_progress=update_progress)
        if not use_frames:
            raise RuntimeError("没有可用关键帧")
        return generate_canonical_json_from_frames(
            frames=use_frames,
            metadata=metadata,
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            update_progress=update_progress,
            work_dir=work_dir,
        )

    if mode == "frames":
        return run_frames()
    if mode == "native":
        return run_native()

    # auto
    try:
        return run_native()
    except Exception as e:
        print(f"[!] native mode failed, fallback to frames: {e}")
        if update_progress:
            update_progress(stage="keyframes", progress=45, message="原生理解失败，回退抽帧模式...")
        return run_frames()


def _safe_get(obj: Any, *keys, default=""):
    if not isinstance(obj, dict):
        return default
    for k in keys:
        if k in obj and obj[k] not in (None, ""):
            return obj[k]
    return default


def render_mode(canonical_data: Dict[str, Any], mode: str = "study_note", show_source: bool = True) -> str:
    data = _normalize_canonical(canonical_data, canonical_data.get("source") or {})
    source = data.get("source", {})
    title = source.get("title") or "未命名视频"
    uploader = source.get("uploader") or "未知作者"
    source_url = source.get("source_url") or ""
    link_url = source_url if isinstance(source_url, str) and source_url.startswith("http") else ""
    summary = data.get("summary") or ""
    understand_mode = data.get("understand_mode") or ""
    native_transcript = data.get("native_transcript") or ""

    if mode == "study_note":
        md = f"# 📚 学习笔记：{title}\n\n"
        if show_source:
            if link_url:
                md += f"> **视频来源**：[{title}]({link_url})  \n"
            else:
                md += f"> **视频来源**：{title}（{source_url or '本地/未知'}）  \n"
            md += f"> **作者/UP主**：{uploader}  \n"
            md += f"> **视频时长**：{source.get('duration_sec', 0)} 秒  \n"
            if understand_mode:
                md += f"> **理解模式**：{understand_mode}  \n"
            md += "\n"

        md += f"## 📌 视频主旨\n\n{summary}\n\n"

        claims = data.get("claims") or []
        if claims:
            md += "## 💡 核心观点与洞察\n\n"
            for c in claims:
                md += f"* **[{_safe_get(c, 'importance', default='重要')}] {_safe_get(c, 'text')}**\n"
            md += "\n"

        chapters = data.get("chapters") or []
        if chapters:
            md += "## 📖 章节要点拆解\n\n"
            for ch in chapters:
                md += (
                    f"### ⏱️ [{_safe_get(ch, 'start_time', default='00:00')} - "
                    f"{_safe_get(ch, 'end_time')}] {_safe_get(ch, 'title')}\n"
                )
                md += f"{_safe_get(ch, 'summary')}\n\n"

        methods = data.get("methods") or []
        if methods:
            md += "## 🛠️ 方法论与操作步骤\n\n"
            for m in methods:
                md += f"### 🔹 {_safe_get(m, 'name')}\n"
                md += f"{_safe_get(m, 'description')}\n\n"
                steps = m.get("steps") if isinstance(m, dict) else []
                if steps:
                    md += "**执行步骤：**\n"
                    for idx, s in enumerate(steps, 1):
                        md += f"{idx}. {s}\n"
                    md += "\n"

        examples = data.get("examples") or []
        if examples:
            md += "## 🔍 案例与示例\n\n"
            for ex in examples:
                md += f"* **{_safe_get(ex, 'title')}**：{_safe_get(ex, 'description')}\n"
            md += "\n"

        actions = data.get("actions") or []
        if actions:
            md += "## 🚀 建议行动项 (Action Items)\n\n"
            for a in actions:
                md += f"- [ ] **[{_safe_get(a, 'priority', default='中')}]** {_safe_get(a, 'item')}\n"
            md += "\n"

        evidence = data.get("evidence") or []
        if evidence and show_source:
            md += "## 📎 证据与时间线锚点\n\n"
            for ev in evidence:
                md += f"* **[{_safe_get(ev, 'timestamp')}]** {_safe_get(ev, 'quote_or_visual_clue')}\n"
            md += "\n"

        if native_transcript and show_source:
            md += "## 🎬 原生视频复述（Stage A）\n\n"
            md += native_transcript.strip() + "\n\n"
        return md

    if mode == "article":
        md = f"# {title}\n\n"
        if show_source and link_url:
            md += f"> 本文基于视频 [{title}]({link_url})（UP主：{uploader}）深度重写而成。\n\n---\n\n"
        elif show_source:
            md += f"> 本文基于视频《{title}》（UP主：{uploader}）深度重写而成。\n\n---\n\n"

        # 核心论点高亮（只取高重要性，突出重点）
        top_claims = [c for c in (data.get("claims") or []) if _safe_get(c, "importance", default="中") in ("高", "high", "HIGH")]
        if top_claims:
            md += "## 🎯 一句话抓住核心\n\n"
            for c in top_claims[:3]:
                md += f"> **{_safe_get(c, 'text')}**\n>\n"
            md += "\n"

        md += f"## 引言\n\n{summary}\n\n"

        # 正文按章节展开
        chapters = data.get("chapters") or []
        if chapters:
            md += "## 正文\n\n"
            for ch in chapters:
                t = _safe_get(ch, "title", default="未命名章节")
                ts = _safe_get(ch, "start_time")
                te = _safe_get(ch, "end_time")
                time_tag = f"（{ts}-{te}）" if (ts or te) else ""
                md += f"### {t}{time_tag}\n\n{_safe_get(ch, 'summary')}\n\n"

        # 方法实操
        methods = data.get("methods") or []
        if methods:
            md += "## 实操指南\n\n"
            for m in methods:
                md += f"### {_safe_get(m, 'name')}\n\n{_safe_get(m, 'description')}\n\n"
                steps = m.get("steps") if isinstance(m, dict) else []
                if steps:
                    for idx, s in enumerate(steps, 1):
                        md += f"{idx}. {s}\n"
                    md += "\n"

        # 案例论据
        examples = data.get("examples") or []
        if examples:
            md += "## 案例与论据\n\n"
            for ex in examples:
                md += f"- **{_safe_get(ex, 'title')}**：{_safe_get(ex, 'description')}\n"
            md += "\n"

        # 行动号召
        actions = data.get("actions") or []
        if actions:
            md += "## 写在最后：你能马上做什么\n\n"
            for a in actions:
                md += f"- {_safe_get(a, 'item')}\n"
            md += "\n"
        return md

    if mode == "cards":
        md = f"# 🎴 知识卡片集：{title}\n\n"
        if show_source:
            md += f"> 来源：{title}（{uploader}）\n\n"

        # 卡片1类：核心观点（按重要性分层，高优先高亮）
        claims = data.get("claims") or []
        if claims:
            md += "## 💡 核心观点卡\n\n"
            core_claims = [c for c in claims if _safe_get(c, "importance", default="中") in ("高", "high", "HIGH")]
            other_claims = [c for c in claims if c not in core_claims]
            for idx, c in enumerate(core_claims, 1):
                md += f"### 🔥 核心观点 {idx}\n\n"
                md += f"> **{_safe_get(c, 'text')}**\n\n"
                ctype = _safe_get(c, "type", default="洞察")
                md += f"*类型：{ctype} · 重要程度：高*\n\n---\n\n"
            for idx, c in enumerate(other_claims, 1):
                md += f"### 观点 {idx}\n\n"
                md += f"> {_safe_get(c, 'text')}\n\n"
                md += f"*重要程度：{_safe_get(c, 'importance', default='中')}*\n\n---\n\n"

        # 卡片2类：方法步骤
        methods = data.get("methods") or []
        if methods:
            md += "## 🛠️ 方法步骤卡\n\n"
            for idx, m in enumerate(methods, 1):
                md += f"### 方法 {idx}：{_safe_get(m, 'name')}\n\n"
                md += f"{_safe_get(m, 'description')}\n\n"
                steps = m.get("steps") if isinstance(m, dict) else []
                if steps:
                    md += "**核心步骤：**\n\n"
                    for s_idx, s in enumerate(steps, 1):
                        md += f"{s_idx}. {s}\n"
                    md += "\n"
                md += "---\n\n"

        # 卡片3类：案例
        examples = data.get("examples") or []
        if examples:
            md += "## 🔍 案例卡\n\n"
            for idx, ex in enumerate(examples, 1):
                md += f"### 案例 {idx}：{_safe_get(ex, 'title')}\n\n"
                md += f"{_safe_get(ex, 'description')}\n\n---\n\n"

        # 卡片4类：行动清单
        actions = data.get("actions") or []
        if actions:
            md += "## 🚀 行动卡\n\n"
            for idx, a in enumerate(actions, 1):
                prio = _safe_get(a, "priority", default="中")
                mark = "🔥" if prio in ("高", "high", "HIGH") else "☐"
                md += f"- {mark} **{_safe_get(a, 'item')}** （优先级：{prio}）\n"
            md += "\n"

        # 卡片5类：证据锚点
        evidence = data.get("evidence") or []
        if evidence and show_source:
            md += "## 📎 证据锚点卡\n\n"
            for idx, ev in enumerate(evidence, 1):
                md += f"- **[{_safe_get(ev, 'timestamp')}]** {_safe_get(ev, 'quote_or_visual_clue')}\n"
            md += "\n"
        return md

    if mode == "teaching_html":
        md = f"# 🎓 教学讲义：{title}\n\n"
        if show_source:
            md += f"> 讲师：{uploader} · 时长 {source.get('duration_sec', 0)} 秒\n\n"
        md += f"## 导读\n\n{summary}\n\n"

        # 学习目标（核心观点转化）
        top_claims = [c for c in (data.get("claims") or []) if _safe_get(c, "importance", default="中") in ("高", "high", "HIGH")]
        if top_claims:
            md += "## 🎯 学习目标\n\n学完本讲，你将掌握：\n\n"
            for c in top_claims:
                md += f"- {_safe_get(c, 'text')}\n"
            md += "\n"

        # 教学章节
        chapters = data.get("chapters") or []
        if chapters:
            md += "## 📚 教学章节\n\n"
            for ch in chapters:
                ts = _safe_get(ch, "start_time")
                te = _safe_get(ch, "end_time")
                time_tag = f" `[{ts}-{te}]`" if (ts or te) else ""
                md += f"### {_safe_get(ch, 'title')}{time_tag}\n\n"
                md += f"{_safe_get(ch, 'summary')}\n\n"

        # 操作示范
        methods = data.get("methods") or []
        if methods:
            md += "## 🛠️ 操作示范\n\n"
            for m in methods:
                md += f"### {_safe_get(m, 'name')}\n\n{_safe_get(m, 'description')}\n\n"
                steps = m.get("steps") if isinstance(m, dict) else []
                if steps:
                    md += "**操作步骤：**\n\n"
                    for idx, s in enumerate(steps, 1):
                        md += f"{idx}. {s}\n"
                    md += "\n"

        # 案例解析
        examples = data.get("examples") or []
        if examples:
            md += "## 🔍 案例解析\n\n"
            for ex in examples:
                md += f"- **{_safe_get(ex, 'title')}**：{_safe_get(ex, 'description')}\n"
            md += "\n"

        # 课后行动
        actions = data.get("actions") or []
        if actions:
            md += "## 📝 课后行动\n\n"
            for a in actions:
                md += f"- [ ] {_safe_get(a, 'item')}\n"
            md += "\n"
        return md

    return f"# {title}\n\n{summary}"
