import pytest
from unittest.mock import MagicMock, patch
from src.core.state import PipelineState
from src.core.graph import screenwriter

@patch("src.agents.pre_production.ChatGoogleGenerativeAI")
def test_screenwriter_chunks_scenes(mock_llm):
    # Setup mock response
    mock_instance = mock_llm.return_value
    mock_response = MagicMock()
    mock_response.content = """
    ```json
    [
        {
            "id": "scene_1",
            "location": "Forest of Shadows",
            "time_of_day": "Dusk",
            "characters": ["Alaric", "Elara"],
            "description": "Alaric and Elara enter the dark forest, looking around cautiously."
        },
        {
            "id": "scene_2",
            "location": "Ancient Temple",
            "time_of_day": "Night",
            "characters": ["Alaric"],
            "description": "Alaric finds an old temple hidden in the trees."
        }
    ]
    ```
    """
    mock_instance.invoke.return_value = mock_response

    # Setup: Initial state
    initial_state: PipelineState = {
        "novel_text": "Long text about a forest and a temple...",
        "current_chapter_id": "ch1",
        "entity_graph": {},
        "scenes": [],
        "current_scene_index": 0,
        "shot_list": [],
        "current_shot_index": 0,
        "retry_count": 0,
        "last_error": None,
        "approved_clips": []
    }
    
    # Act
    new_state = screenwriter(initial_state)
    
    # Assert
    assert len(new_state["scenes"]) == 2
    assert new_state["scenes"][0].id == "scene_1"
    assert new_state["scenes"][1].location == "Ancient Temple"
    assert "Alaric" in new_state["scenes"][0].characters
