import os
import pytest

from main import run_pipeline

_HERE = os.path.dirname(__file__)
_NOVEL_PATH = os.path.join(_HERE, "test_project", "novel.txt")


@pytest.mark.skip(reason="Uses real API models - run explicitly with --run-real-tests")
def test_real_pipeline_execution():
    with open(_NOVEL_PATH, "r", encoding="utf-8") as f:
        text = f.read(1000)

    final_state = run_pipeline(text)

    assert len(final_state["entity_graph"]) > 0
    assert len(final_state["scenes"]) > 0
    assert len(final_state["shot_list"]) > 0
    assert len(final_state["approved_clips"]) > 0

    final_video_path = final_state.get("final_video_path")
    assert final_video_path is not None
    assert os.path.exists(final_video_path)
    assert os.path.getsize(final_video_path) > 0
