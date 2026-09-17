from pathlib import Path


def test_wheel_configuration_includes_agent_skill_files():
    config = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "[tool.setuptools.data-files]" in config
    assert "skills/videomind/SKILL.md" in config
    assert "skills/videomind/scripts/*.py" in config
    assert "skills/videomind/references/*.md" in config
