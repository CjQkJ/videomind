import os
import subprocess
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.sanitize_job_secrets import sanitize_payload


def test_sanitize_script_is_directly_executable_from_outside_backend(tmp_path):
    script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scripts", "sanitize_job_secrets.py")
    )
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--apply" in completed.stdout


def test_sanitize_payload_removes_server_owned_upstream_fields_recursively():
    source = {
        "input": {"type": "upload"},
        "options": {
            "api_key": "secret",
            "api_url": "https://attacker.invalid",
            "model": "client-model",
            "max_duration_sec": 999999,
            "understand_mode": "frames",
            "language": "zh-CN",
        },
        "nested": [{"api_key": "another-secret", "keep": True}],
    }

    cleaned = sanitize_payload(source)

    serialized = str(cleaned)
    for forbidden in (
        "api_key",
        "api_url",
        "client-model",
        "max_duration_sec",
        "understand_mode",
        "another-secret",
    ):
        assert forbidden not in serialized
    assert cleaned["options"]["language"] == "zh-CN"
    assert cleaned["nested"][0]["keep"] is True
    assert source["options"]["api_key"] == "secret"
