import json

import pytest
import requests

from videomind import config
from videomind.client import Client, VideoMindError
from videomind.config import Config


def test_environment_base_url_overrides_config_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "api_key": "vw_file_key",
                "base_url": "https://file.example",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "config_path", lambda: path)
    monkeypatch.setenv(config.ENV_KEY, "vw_env_key")
    monkeypatch.setenv(config.ENV_BASE, "https://env.example")

    loaded = config.load()

    assert loaded.api_key == "vw_env_key"
    assert loaded.base_url == "https://env.example"


@pytest.mark.parametrize(
    "configured_url",
    [
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8000/",
        "https://video.example.com",
    ],
)
def test_load_preserves_configured_base_url(tmp_path, monkeypatch, configured_url):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"api_key": "vw_file_key", "base_url": configured_url}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "config_path", lambda: path)
    monkeypatch.delenv(config.ENV_KEY, raising=False)
    monkeypatch.delenv(config.ENV_BASE, raising=False)

    loaded = config.load()

    assert loaded.base_url == configured_url


@pytest.mark.parametrize(
    ("env_url", "expected"),
    [
        ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("https://self-hosted.example", "https://self-hosted.example"),
    ],
)
def test_environment_base_url_is_used_verbatim(tmp_path, monkeypatch, env_url, expected):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setenv(config.ENV_KEY, "vw_env_key")
    monkeypatch.setenv(config.ENV_BASE, env_url)

    assert config.load().base_url == expected


def test_save_without_base_url_uses_default(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "config_path", lambda: path)

    saved = config.save("vw_test")

    assert saved.base_url == config.DEFAULT_BASE_URL
    assert json.loads(path.read_text(encoding="utf-8"))["base_url"] == saved.base_url


def test_save_preserves_custom_base_url(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "config_path", lambda: path)

    local = config.save("vw_test", "http://127.0.0.1:8000")
    custom = config.save("vw_test", "https://self-hosted.example")

    assert local.base_url == "http://127.0.0.1:8000"
    assert custom.base_url == "https://self-hosted.example"
    assert json.loads(path.read_text(encoding="utf-8"))["base_url"] == custom.base_url


def test_network_errors_are_wrapped_as_videomind_error(monkeypatch):
    client = Client(Config(api_key="vw_test", base_url="https://api.example"))

    def fail_request(*_args, **_kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(client.session, "request", fail_request)

    with pytest.raises(VideoMindError, match="网络"):
        client.health()


def test_direct_config_construction_targets_configured_url(monkeypatch):
    client = Client(
        Config(api_key="vw_test", base_url="https://video.example.com")
    )
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "ok"}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, kwargs=kwargs)
        return Response()

    monkeypatch.setattr(client.session, "request", fake_request)

    client.health()

    assert captured["url"] == "https://video.example.com/api/v1/health"


def test_upload_posts_multipart_and_returns_file_id(tmp_path, monkeypatch):
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"video-data")
    client = Client(Config(api_key="vw_test", base_url="https://api.example"))
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"file_id": "uploaded_file.mp4", "size": 10}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, kwargs=kwargs)
        return Response()

    monkeypatch.setattr(client.session, "request", fake_request)

    result = client.upload(video)

    assert result["file_id"] == "uploaded_file.mp4"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/api/v1/uploads")
    assert captured["kwargs"]["files"]["file"][0] == "lesson.mp4"
