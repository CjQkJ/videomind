import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pipeline


def test_pipeline_has_no_hardcoded_upstream_api_key():
    assert pipeline.DEFAULT_API_KEY == ""
