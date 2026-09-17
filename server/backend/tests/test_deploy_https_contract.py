from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "apply_release.sh"


def test_release_requires_valid_tls_before_stopping_services():
    source = SCRIPT.read_text(encoding="utf-8")

    validation_at = source.index("openssl x509 -checkend 86400")
    stop_at = source.index("systemctl stop video_workbench_worker_2.service")

    assert validation_at < stop_at
    assert 'VIDEOMIND_ALLOW_HTTP_BOOTSTRAP:-0' in source
    assert "refusing deployment: valid TLS certificate" in source
    assert 'nginx_release_conf="$release_dir/deploy/nginx-video_workbench-https.conf"' in source
