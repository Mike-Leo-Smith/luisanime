import pytest
from unittest.mock import MagicMock, patch
from src.core.state import PipelineState, SceneIR, Shot
from src.core.graph import director

@patch("src.core.graph.ChatGoogleGenerativeAI")
def test_director_generates_shot_list(mock_llm):
    # Setup mock response
    mock_instance = mock_llm.return_value
    mock_response = MagicMock()
    mock_response.content = """
    ```json
    [
        {
            "id": "shot_1_1",
            "scene_id": "scene_1",
            "prompt": "Medium shot of Alaric entering the forest.",
            "camera_movement": "Steady pan",
            "duration": 5.0
        },
        {
            "id": "shot_1_2",
            "scene_id": "scene_1",
            "prompt": "Close-up of Alaric's cautious expression.",
            "camera_movement": "Static",
            "duration": 3.0
        }
    ]
    ```
    """
    mock_instance.invoke.return_value = mock_response

    # Setup: Initial state with one scene
    scene = SceneIR(
        id="scene_1",
        location="Forest of Shadows",
        time_of_day="Dusk",
        characters=["Alaric"],
        description="Alaric enters the dark forest."
    )
    initial_state: PipelineState = {
        "novel_text": "...",
        "current_chapter_id": "ch1",
        "entity_graph": {},
        "scenes": [scene],
        "current_scene_index": 0,
        "shot_list": [],
        "current_shot_index": 0,
        "retry_count": 0,
        "last_error": None,
        "approved_clips": []
    }
    
    # Act
    new_state = director(initial_state)
    
    # Assert
    assert len(new_state["shot_list"]) == 2
    assert new_state["shot_list"][0].id == "shot_1_1"
    assert new_state["shot_list"][1].camera_movement == "Static"
    assert new_state["shot_list"][0].scene_id == "scene_1"
