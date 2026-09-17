"""Execute a single job pipeline (used by worker)."""
from __future__ import annotations

import glob
import json
import os
import shutil
import traceback
from html import escape
from typing import Any, Dict, Optional

from app.config import get_settings
from app.db import SessionLocal
from app.models import JobRow, utcnow
from app.segment import cut_segment, plan_segments, probe_duration_seconds


def _update_job(db, job_id: str, **fields):
    row = db.query(JobRow).filter(JobRow.job_id == job_id).first()
    if not row:
        return
    # terminal-state guard: a stale thread (e.g. requeued lease) must not
    # resurrect a job that already reached failed/succeeded
    if row.status in ("failed", "succeeded") and fields.get("status", row.status) not in ("failed", "succeeded"):
        return
    for k, v in fields.items():
        if hasattr(row, k):
            setattr(row, k, v)
    row.updated_at = utcnow()
    db.commit()


def _cleanup_job_media(work_dir: str) -> int:
    """Remove large media files after a job reaches a terminal state.

    Keeps results (result.json/md/html, transcripts, metadata, status) so
    history/rerender stay functional; deletes videos and frame dirs that
    would otherwise fill the disk (each job holds 50MB-1GB).
    """
    if not os.path.isdir(work_dir):
        return 0
    freed = 0
    for pat in ("input_video.*", "native_input*.mp4", "upload_src.*"):
        for f in glob.glob(os.path.join(work_dir, pat)):
            try:
                freed += os.path.getsize(f)
                os.remove(f)
            except OSError:
                pass
    for sub in ("segments", "frames"):
        p = os.path.join(work_dir, sub)
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    try:
                        freed += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
            try:
                shutil.rmtree(p)
            except OSError:
                pass
    return freed


def _mark_failed(db, job_id: str, message: str, work_dir: Optional[str] = None) -> None:
    """Best-effort failure marking; retries once because the first attempt can
    itself fail on 'database or disk is full' — the very condition that
    orphaned jobs in 'running' state before. Between attempts, media files are
    cleaned to free disk space when possible."""
    for attempt in range(2):
        try:
            db.rollback()
            _update_job(
                db,
                job_id,
                status="failed",
                stage="failed",
                message=message,
                error=message,
                finished_at=utcnow(),
            )
            return
        except Exception:
            traceback.print_exc()
            if attempt == 0 and work_dir:
                # free disk space then retry the DB write once
                try:
                    _cleanup_job_media(work_dir)
                except Exception:
                    traceback.print_exc()


def run_job(job_id: str) -> None:
    from pipeline import (
        process_video_input,
        generate_canonical_json,
        render_mode,
        antigravity_native_video_understand,
        structure_from_transcript,
        prepare_video_for_native,
        DEFAULT_API_URL,
        DEFAULT_API_KEY,
        DEFAULT_MODEL,
        UNDERSTAND_MODE,
    )

    s = get_settings()
    jobs_dir = s.jobs_dir
    uploads_dir = s.uploads_dir
    os.makedirs(jobs_dir, exist_ok=True)

    # defined before try so the failure path can always reference it
    work_dir = os.path.join(jobs_dir, job_id)
    os.makedirs(work_dir, exist_ok=True)

    db = SessionLocal()
    try:
        row = db.query(JobRow).filter(JobRow.job_id == job_id).first()
        if not row:
            return
        req = row.request_json or {}
        input_type = row.input_type or (req.get("input") or {}).get("type")
        mode = row.mode or "study_note"
        options = row.options_json or req.get("options") or {}
        api_url = s.openai_base_url or DEFAULT_API_URL
        api_key = s.openai_api_key or DEFAULT_API_KEY
        from app.runtime_config import effective_default_model
        model = effective_default_model() or DEFAULT_MODEL
        understand_mode = (s.understand_mode or UNDERSTAND_MODE or "native").lower()
        show_source = options.get("show_source", True)
        max_dur = int(s.max_video_duration_sec)
        if not api_key:
            raise RuntimeError("服务器未配置上游 API Key")

        def progress(stage, progress, message):
            _update_job(
                db,
                job_id,
                status="running",
                stage=stage,
                progress=int(progress),
                message=message,
            )

        _update_job(
            db,
            job_id,
            status="running",
            stage="download",
            progress=5,
            message="开始处理...",
            started_at=utcnow(),
            error=None,
        )

        if input_type == "bilibili_url":
            source_val = row.input_url or (req.get("input") or {}).get("url")
        else:
            fid = row.input_file_id or (req.get("input") or {}).get("file_id")
            source_val = os.path.join(uploads_dir, fid)

        metadata = process_video_input(input_type, source_val, work_dir, update_progress=progress)
        duration = float(metadata.get("duration_sec") or probe_duration_seconds(metadata["local_video_path"]))
        if duration <= 0:
            duration = float(metadata.get("duration_sec") or 0)
        if duration > max_dur:
            raise RuntimeError(f"视频时长 {int(duration)}s 超过上限 {max_dur}s（最长 4 小时）")

        metadata["duration_sec"] = int(duration)
        _update_job(db, job_id, metadata_json=metadata)

        video_path = metadata["local_video_path"]
        spans = plan_segments(
            duration,
            threshold=s.segment_threshold_seconds,
            seg=s.segment_seconds,
            overlap=s.segment_overlap_seconds,
        )
        _update_job(db, job_id, segment_total=len(spans), segment_done=0)

        # Native multi-segment path
        if understand_mode in ("native", "auto") and len(spans) > 1:
            transcripts = []
            seg_dir = os.path.join(work_dir, "segments")
            os.makedirs(seg_dir, exist_ok=True)
            for i, (st, en) in enumerate(spans, start=1):
                progress(
                    "ai_extraction",
                    20 + int(60 * (i - 1) / max(len(spans), 1)),
                    f"原生分段理解 {i}/{len(spans)} ({int(st)}s-{int(en)}s)...",
                )
                seg_path = os.path.join(seg_dir, f"seg_{i:03d}.mp4")
                cut_segment(video_path, st, en, seg_path)
                if not os.path.exists(seg_path) or os.path.getsize(seg_path) < 1024:
                    raise RuntimeError(f"分段 {i} 切割失败")
                seg_meta = dict(metadata)
                seg_meta["title"] = f"{metadata.get('title')} [段{i}/{len(spans)}]"
                # point native understand at segment file
                try:
                    text = antigravity_native_video_understand(
                        video_path=seg_path,
                        metadata=seg_meta,
                        api_url=api_url,
                        api_key=api_key,
                        model_name=model,
                        update_progress=None,
                        work_dir=os.path.join(seg_dir, f"work_{i:03d}"),
                    )
                except Exception as e:
                    # retry once
                    text = antigravity_native_video_understand(
                        video_path=seg_path,
                        metadata=seg_meta,
                        api_url=api_url,
                        api_key=api_key,
                        model_name=model,
                        update_progress=None,
                        work_dir=os.path.join(seg_dir, f"work_{i:03d}_retry"),
                    )
                transcripts.append(f"\n\n## 分段 {i}/{len(spans)} ({int(st)}s - {int(en)}s)\n\n{text}")
                _update_job(db, job_id, segment_done=i)

            full_transcript = "\n".join(transcripts)
            with open(os.path.join(work_dir, "native_transcript.md"), "w", encoding="utf-8") as f:
                f.write(full_transcript)
            progress("ai_extraction", 85, "分段复述完成，正在结构化...")
            canonical = structure_from_transcript(
                transcript=full_transcript,
                metadata=metadata,
                api_url=api_url,
                api_key=api_key,
                model_name=model,
                update_progress=progress,
                work_dir=work_dir,
            )
            canonical["understand_mode"] = "native"
            canonical["segment_total"] = len(spans)
        else:
            # single-shot (native or frames) via existing entry
            frames = []
            if understand_mode == "frames":
                from pipeline import extract_keyframes

                frames = extract_keyframes(video_path, work_dir, update_progress=progress)
            try:
                canonical = generate_canonical_json(
                    frames,
                    metadata,
                    api_url=api_url,
                    api_key=api_key,
                    model_name=model,
                    update_progress=progress,
                    work_dir=work_dir,
                    understand_mode=understand_mode,
                )
            except Exception:
                if understand_mode == "auto":
                    from pipeline import extract_keyframes

                    frames = extract_keyframes(video_path, work_dir, update_progress=progress)
                    canonical = generate_canonical_json(
                        frames,
                        metadata,
                        api_url=api_url,
                        api_key=api_key,
                        model_name=model,
                        update_progress=progress,
                        work_dir=work_dir,
                        understand_mode="frames",
                    )
                else:
                    raise
            _update_job(db, job_id, segment_done=1, segment_total=max(1, len(spans)))

        json_path = os.path.join(work_dir, "result.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(canonical, f, ensure_ascii=False, indent=2)

        progress("rendering", 92, "正在渲染 Markdown...")
        md = render_mode(canonical, mode=mode, show_source=bool(show_source))
        # teaching_html extra artifact
        if mode == "teaching_html":
            html = _teaching_html(canonical)
            with open(os.path.join(work_dir, "result.html"), "w", encoding="utf-8") as f:
                f.write(html)
        with open(os.path.join(work_dir, "result.md"), "w", encoding="utf-8") as f:
            f.write(md)

        _update_job(
            db,
            job_id,
            status="succeeded",
            stage="completed",
            progress=100,
            message="解析与渲染完成！",
            finished_at=utcnow(),
            metadata_json=metadata,
        )
    except Exception as e:
        traceback.print_exc()
        _mark_failed(db, job_id, f"处理失败: {e}", work_dir=work_dir)
    finally:
        # always free the large media files once the job is terminal;
        # results (result.*/transcripts/metadata) are kept for history
        try:
            if os.path.isdir(work_dir):
                _cleanup_job_media(work_dir)
        except Exception:
            traceback.print_exc()
        db.close()


def _teaching_html(data: dict) -> str:
    def safe(v, d=""):
        value = d if v in (None, "", []) else v
        return escape(str(value), quote=True)

    src = data.get("source") or {}
    title = safe(src.get("title"), "课程讲义")
    uploader = safe(src.get("uploader"))
    summary = safe(data.get("summary"))
    chapters = data.get("chapters") or []
    methods = data.get("methods") or []
    examples = data.get("examples") or []
    actions = data.get("actions") or []
    claims = data.get("claims") or []

    parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>",
        f"<title>{title}</title>",
        "<style>",
        "body{font-family:system-ui,'PingFang SC','Microsoft YaHei',sans-serif;max-width:920px;margin:40px auto;padding:0 20px;line-height:1.8;color:#18181b;background:#fff}",
        "h1{font-size:2rem;background:linear-gradient(135deg,#10b981,#fbbf24);-webkit-background-clip:text;-webkit-text-fill-color:transparent}",
        "h2{margin-top:2.4rem;border-bottom:2px solid #10b981;padding-bottom:8px;color:#047857;font-size:1.4rem}",
        "h3{margin-top:1.4rem;color:#18181b}",
        ".meta{color:#71717a;font-size:0.9rem;margin:-4px 0 24px}",
        ".card{background:#f7fee7;border:1px solid #bbf7d0;border-radius:14px;padding:18px 22px;margin:14px 0}",
        ".card h3{margin-top:0}",
        ".obj{background:#fef9c3;border:1px solid #fde047;border-radius:14px;padding:18px 22px;margin:18px 0}",
        ".obj ul{margin:8px 0}",
        ".muted{color:#71717a;font-size:0.85rem;margin-bottom:6px}",
        ".step{background:#ecfdf5;border-radius:10px;padding:12px 18px;margin:10px 0}",
        ".actions li{margin:6px 0}",
        "blockquote{border-left:4px solid #10b981;background:#f0fdf4;margin:10px 0;padding:10px 16px;border-radius:0 10px 10px 0}",
        "</style></head><body>",
        f"<h1>🎓 {title}</h1>",
    ]
    if uploader:
        parts.append(f"<div class='meta'>讲师：{uploader}</div>")
    if summary:
        parts.append(f"<blockquote><strong>导读</strong>：{summary}</blockquote>")

    # 学习目标
    core_claims = [c for c in claims if str(c.get("importance", "中")).lower() in ("高", "high")]
    if core_claims:
        parts.append("<div class='obj'><h2>🎯 学习目标</h2><p>学完本讲，你将掌握：</p><ul>")
        for c in core_claims[:6]:
            parts.append(f"<li>{safe(c.get('text'))}</li>")
        parts.append("</ul></div>")

    # 教学章节
    if chapters:
        parts.append("<h2>📚 教学章节</h2>")
        for ch in chapters:
            ts, te = safe(ch.get("start_time")), safe(ch.get("end_time"))
            time_tag = f"<div class='muted'>{ts} - {te}</div>" if (ts or te) else ""
            parts.append(
                f"<div class='card'><h3>{safe(ch.get('title'))}</h3>{time_tag}"
                f"<p>{safe(ch.get('summary'))}</p></div>"
            )

    # 操作示范
    if methods:
        parts.append("<h2>🛠️ 操作示范</h2>")
        for m in methods:
            steps = m.get("steps") or []
            ol = "".join(f"<li>{safe(s)}</li>" for s in steps)
            parts.append(
                f"<div class='card'><h3>{safe(m.get('name'))}</h3>"
                f"<p>{safe(m.get('description'))}</p>"
                f"<ol>{ol}</ol></div>"
            )

    # 案例解析
    if examples:
        parts.append("<h2>🔍 案例解析</h2>")
        for ex in examples:
            parts.append(
                f"<div class='card'><h3>{safe(ex.get('title'))}</h3>"
                f"<p>{safe(ex.get('description'))}</p></div>"
            )

    # 课后行动
    if actions:
        parts.append("<h2>📝 课后行动</h2><ul class='actions'>")
        for a in actions:
            parts.append(f"<li>☐ {safe(a.get('item'))}</li>")
        parts.append("</ul>")

    parts.append("</body></html>")
    return "\n".join(parts)
