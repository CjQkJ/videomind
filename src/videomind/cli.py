"""``videomind`` 命令行界面。

支持「一条龙」：``videomind <B站链接>``（自动转发到 ``run``）即提交→等待→保存笔记到本地。
另有 submit / status / result / jobs / wait / config / health / whoami 等子命令。
"""
from __future__ import annotations

import json as _json
import sys
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .client import Client, VideoMindError
from .config import DEFAULT_BASE_URL, config_path, load, save


class _OneShotGroup(typer.core.TyperGroup):
    """未知的首个参数转发给 ``run`` 命令，从而支持 ``videomind <url>``。"""

    def resolve_command(self, ctx, args):
        cmd_name = args[0] if args else ""
        if (
            cmd_name
            and not cmd_name.startswith("-")
            and cmd_name not in self.commands
        ):
            run_cmd = self.commands.get("run")
            if run_cmd is not None:
                return run_cmd.name, run_cmd, args
        return super().resolve_command(ctx, args)


app = typer.Typer(
    name="videomind",
    cls=_OneShotGroup,
    help="🎬 VideoMind — 把 B 站/本地视频变成结构化学习笔记、文章、卡片。",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=False,
)
config_app = typer.Typer(help="管理本地配置（API Key / 服务地址）", no_args_is_help=True)
app.add_typer(config_app, name="config")


# -- 工具函数 --------------------------------------------------------------
def _client() -> Client:
    try:
        return Client(load())
    except SystemExit as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc


def _abort(message: str, code: int = 1) -> None:
    typer.secho(message, err=True, fg=typer.colors.RED)
    raise typer.Exit(code=code)


def _echo_json(obj: dict) -> None:
    typer.echo(_json.dumps(obj, ensure_ascii=False, indent=2))


# -- 版本 / 默认回调 -------------------------------------------------------
def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"videomind {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="显示版本号",
    ),
) -> None:
    """🎬 VideoMind — 把 B 站/本地视频变成结构化学习笔记、文章、卡片。"""
    if ctx.invoked_subcommand is None and not version:
        typer.echo(ctx.get_help())
        raise typer.Exit()


# -- config ----------------------------------------------------------------
@config_app.command("set-key")
def config_set_key(
    key: str = typer.Argument(..., help="vw_ 开头的 API Key"),
    base_url: str = typer.Option(
        DEFAULT_BASE_URL, "--base-url", help="服务地址（自部署时修改）"
    ),
) -> None:
    """保存 API Key 到本地配置文件。"""
    cfg = save(key, base_url)
    typer.secho("✓ 已保存配置", fg=typer.colors.GREEN)
    typer.echo(f"  位置：{config_path()}")
    typer.echo(f"  地址：{cfg.base_url}")


@config_app.command("show")
def config_show() -> None:
    """查看当前配置（Key 脱敏显示）。"""
    try:
        cfg = load()
    except SystemExit as exc:
        _abort(str(exc))
        return
    masked = cfg.api_key[:8] + "…" if len(cfg.api_key) > 8 else "***"
    typer.echo(f"base_url = {cfg.base_url}")
    typer.echo(f"api_key  = {masked}")
    typer.echo(f"file     = {config_path()}")


@config_app.command("path")
def config_path_cmd() -> None:
    """打印配置文件路径。"""
    typer.echo(config_path())


# -- 一条龙：run / videomind <url> -----------------------------------------
@app.command(
    "run",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def run_cmd(
    url: str = typer.Argument(..., help="B 站视频链接或本地视频路径"),
    mode: str = typer.Option(
        "study_note", "--mode", "-m", help="study_note|article|cards|teaching_html"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="保存路径：目录或 .md/.json/.html 文件"
    ),
    poll: int = typer.Option(5, "--poll", help="轮询间隔（秒）"),
    show_source: bool = typer.Option(
        True, "--show-source/--no-source", help="笔记是否带来源时间戳"
    ),
    language: str = typer.Option("zh-CN", "--language", help="输出语言"),
) -> None:
    """一条龙：上传/提交 → 等待 → 保存结果。"""
    _oneshot(
        url=url,
        mode=mode,
        output=output,
        poll=poll,
        show_source=show_source,
        language=language,
    )


def _oneshot(
    *,
    url: str,
    mode: str,
    output: Optional[Path],
    poll: int,
    show_source: bool,
    language: str,
) -> None:
    client = _client()
    try:
        local_path = Path(url)
        if local_path.is_file():
            typer.echo(f"  正在上传本地视频：{local_path.name}")
            uploaded = client.upload(local_path)
            created = client.submit(
                file_id=uploaded["file_id"],
                mode=mode,
                show_source=show_source,
                language=language,
            )
        else:
            created = client.submit(
                url=url, mode=mode, show_source=show_source, language=language
            )
    except VideoMindError as exc:
        _abort(str(exc))
        return
    job_id = created["job_id"]
    typer.secho(f"✓ 已提交 {job_id}", fg=typer.colors.GREEN)
    if not created.get("can_start_now"):
        typer.echo(f"  排队中：{created.get('queue_reason', '等待槽位')}")

    def on_progress(data: dict) -> None:
        typer.echo(
            f"  [{data.get('status')}] {data.get('progress', 0):>3}%  {data.get('message', '')}"
        )

    try:
        final = client.wait(job_id, on_progress=on_progress, poll=poll)
    except VideoMindError as exc:
        _abort(str(exc))
        return

    if final.get("status") != "succeeded":
        _abort(f"任务失败：{final.get('message', '未知原因')}")

    title = final.get("metadata", {}).get("title", job_id)
    typer.secho(f"✓ 完成：{title}", fg=typer.colors.GREEN)
    _save_results(client, job_id, output, include_html=mode == "teaching_html")


def _save_results(
    client: Client,
    job_id: str,
    output: Optional[Path],
    *,
    include_html: bool = False,
) -> None:
    """根据 output 类型把结果写到磁盘。"""
    if output and output.suffix:
        fmt = output.suffix.lstrip(".").replace("markdown", "md")
        if fmt not in ("md", "json", "html"):
            _abort(f"不支持的输出后缀 .{fmt}（仅支持 md/json/html）")
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(client.result_bytes(job_id, fmt))
        typer.echo(f"✓ 已保存 {output}")
        return

    out_dir = output if output else Path(job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.md").write_bytes(client.result_bytes(job_id, "md"))
    (out_dir / "result.json").write_bytes(client.result_bytes(job_id, "json"))
    saved = ["result.md", "result.json"]
    if include_html:
        (out_dir / "result.html").write_bytes(client.result_bytes(job_id, "html"))
        saved.append("result.html")
    typer.echo(f"✓ 已保存到 {out_dir}/  ({' + '.join(saved)})")


# -- 其他子命令 ------------------------------------------------------------
@app.command()
def submit(
    url: str = typer.Argument(..., help="B 站视频链接"),
    mode: str = typer.Option("study_note", "--mode", "-m"),
    show_source: bool = typer.Option(True, "--show-source/--no-source"),
    language: str = typer.Option("zh-CN"),
) -> None:
    """提交任务并立即返回 job_id（不等待）。"""
    client = _client()
    try:
        data = client.submit(
            url=url, mode=mode, show_source=show_source, language=language
        )
    except VideoMindError as exc:
        _abort(str(exc))
        return
    typer.echo(data["job_id"])
    typer.echo(
        f"(status={data.get('status')} can_start_now={data.get('can_start_now')})",
        err=True,
    )


@app.command()
def status(job_id: str = typer.Argument(..., help="job_id")) -> None:
    """查询任务进度。"""
    client = _client()
    try:
        _echo_json(client.get(job_id))
    except VideoMindError as exc:
        _abort(str(exc))


@app.command()
def wait(
    job_id: str = typer.Argument(...),
    poll: int = typer.Option(5, "--poll"),
    timeout: int = typer.Option(1800, "--timeout"),
) -> None:
    """轮询直到任务成功或失败。"""
    client = _client()

    def on_progress(data: dict) -> None:
        typer.echo(
            f"  [{data.get('status')}] {data.get('progress', 0):>3}%  {data.get('message', '')}"
        )

    try:
        final = client.wait(job_id, on_progress=on_progress, poll=poll, timeout=timeout)
    except VideoMindError as exc:
        _abort(str(exc))
        return
    ok = final.get("status") == "succeeded"
    typer.secho(
        ("✓ 成功" if ok else "✗ 失败") + f"  {final.get('message', '')}",
        fg=typer.colors.GREEN if ok else typer.colors.RED,
    )


@app.command()
def result(
    job_id: str = typer.Argument(...),
    fmt: str = typer.Option("md", "--format", "-f", help="md|json|html"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """下载结果产物。"""
    client = _client()
    try:
        content = client.result_bytes(job_id, fmt)
    except VideoMindError as exc:
        _abort(str(exc))
        return
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        typer.echo(f"✓ 已保存 {output}")
    else:
        try:
            sys.stdout.write(content.decode("utf-8"))
        except UnicodeEncodeError:
            sys.stdout.buffer.write(content)


@app.command("jobs")
def jobs_cmd(
    limit: int = typer.Option(30, "--limit", "-n"),
) -> None:
    """列出历史任务。"""
    client = _client()
    try:
        data = client.list_jobs(limit=limit)
    except VideoMindError as exc:
        _abort(str(exc))
        return
    items = data.get("items", [])
    if not items:
        typer.echo("（暂无任务）")
        return
    for it in items:
        title = it.get("metadata", {}).get("title", "")
        typer.echo(
            f"{it['job_id']}  {str(it.get('status')):10}  "
            f"{it.get('progress', 0):>3}%  {title}"
        )


@app.command()
def health() -> None:
    """检查服务状态与配额默认值。"""
    client = _client()
    try:
        _echo_json(client.health())
    except VideoMindError as exc:
        _abort(str(exc))


@app.command()
def whoami() -> None:
    """验证当前 API Key 并显示账号信息。"""
    client = _client()
    try:
        _echo_json(client.me())
    except VideoMindError as exc:
        _abort(str(exc))


if __name__ == "__main__":
    app()
