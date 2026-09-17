import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.job_runner import _teaching_html


def test_teaching_html_escapes_model_generated_fields():
    malicious = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    rendered = _teaching_html(
        {
            "source": {"title": malicious, "uploader": malicious},
            "summary": malicious,
            "chapters": [
                {
                    "title": malicious,
                    "summary": malicious,
                    "start_time": malicious,
                    "end_time": malicious,
                }
            ],
            "methods": [
                {
                    "name": malicious,
                    "description": malicious,
                    "steps": [malicious],
                }
            ],
            "examples": [{"title": malicious, "description": malicious}],
            "actions": [{"item": malicious}],
            "claims": [{"importance": "high", "text": malicious}],
        }
    )

    assert "<script>" not in rendered
    assert "<img src=x" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "&lt;img src=x" in rendered
