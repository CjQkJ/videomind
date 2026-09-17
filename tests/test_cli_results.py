from pathlib import Path

from videomind import cli
from videomind.cli import _save_results


class FakeClient:
    def __init__(self):
        self.formats = []

    def result_bytes(self, _job_id: str, fmt: str) -> bytes:
        self.formats.append(fmt)
        return fmt.encode("ascii")


def test_teaching_html_default_output_downloads_html(tmp_path):
    client = FakeClient()
    output = tmp_path / "result"

    _save_results(
        client,
        "job_test",
        output,
        include_html=True,
    )

    assert client.formats == ["md", "json", "html"]
    assert (output / "result.html").read_bytes() == b"html"


def test_oneshot_local_path_uploads_before_submitting(tmp_path, monkeypatch):
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "notes"

    class LocalClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.uploaded = None
            self.submitted = None

        def upload(self, path):
            self.uploaded = Path(path)
            return {"file_id": "uploaded_lesson.mp4"}

        def submit(self, **kwargs):
            self.submitted = kwargs
            return {"job_id": "job_local", "status": "queued", "can_start_now": True}

        def wait(self, _job_id, **_kwargs):
            return {"status": "succeeded", "metadata": {"title": "Local lesson"}}

    client = LocalClient()
    monkeypatch.setattr(cli, "_client", lambda: client)

    cli._oneshot(
        url=str(video),
        mode="study_note",
        output=output,
        poll=0,
        show_source=True,
        language="zh-CN",
    )

    assert client.uploaded == video
    assert client.submitted["file_id"] == "uploaded_lesson.mp4"
    assert client.submitted.get("url") is None
