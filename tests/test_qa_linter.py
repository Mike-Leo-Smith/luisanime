import pytest
from unittest.mock import MagicMock, patch
from src.core.state import PipelineState, Shot
from src.core.graph import qa_linter


@patch("src.agents.production.requests.get")
@patch("src.agents.production.ChatGoogleGenerativeAI")
def test_qa_linter_approves_good_video(mock_llm, mock_get):
    # Mock VLM response for a "good" video
    mock_instance = mock_llm.return_value
    mock_response = MagicMock()
    mock_response.content = """
    ```json
    {
        "status": "approved",
        "reason": "Correct characters, no topological artifacts, consistent background."
    }
    ```
    """
    mock_instance.invoke.return_value = mock_response

    mock_get_response = MagicMock()
    mock_get_response.iter_content.return_value = [b"fake_video_data"]
    mock_get.return_value = mock_get_response

    initial_shot = Shot(
        id="shot_1_1",
        scene_id="scene_1",
        prompt="A man in the forest",
        camera_movement="Static",
        duration=3.0,
        video_url="https://example.com/good.mp4",
        status="animated",
    )

    initial_state: PipelineState = {
        "novel_text": "...",
        "current_chapter_id": "ch1",
        "entity_graph": {},
        "scenes": [],
        "current_scene_index": 0,
        "shot_list": [initial_shot],
        "current_shot_index": 0,
        "retry_count": 0,
        "last_error": None,
        "approved_clips": [],
    }

    # Act
    new_state = qa_linter(initial_state)

    # Assert
    assert new_state["shot_list"][0].status == "approved"
    assert "shot_1_1.mp4" in new_state["approved_clips"][0]
    mock_get.assert_called_once_with(
        "https://example.com/good.mp4", stream=True, timeout=10
    )


@patch("src.agents.production.ChatGoogleGenerativeAI")
def test_qa_linter_rejects_bad_video(mock_llm):
    # Mock VLM response for a "bad" video (e.g., limb melting)
    mock_instance = mock_llm.return_value
    mock_response = MagicMock()
    mock_response.content = """
    ```json
    {
        "status": "rejected",
        "reason": "Topological collapse detected: characters' limbs are melting into the background."
    }
    ```
    """
    mock_instance.invoke.return_value = mock_response

    initial_shot = Shot(
        id="shot_1_1",
        scene_id="scene_1",
        prompt="A man in the forest",
        camera_movement="Static",
        duration=3.0,
        video_url="https://example.com/bad.mp4",
        status="animated",
    )

    initial_state: PipelineState = {
        "novel_text": "...",
        "current_chapter_id": "ch1",
        "entity_graph": {},
        "scenes": [],
        "current_scene_index": 0,
        "shot_list": [initial_shot],
        "current_shot_index": 0,
        "retry_count": 1,
        "last_error": None,
        "approved_clips": [],
    }

    # Act
    new_state = qa_linter(initial_state)

    # Assert
    assert new_state["shot_list"][0].status == "qa_failed"
    assert new_state["retry_count"] == 2
