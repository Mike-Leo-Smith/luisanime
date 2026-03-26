import pytest
from unittest.mock import MagicMock, patch
from src.core.state import PipelineState
from src.core.graph import lore_master

@patch("src.agents.pre_production.ChatGoogleGenerativeAI")
def test_lore_master_extracts_entities(mock_llm):
    # Setup mock response
    mock_instance = mock_llm.return_value
    mock_response = MagicMock()
    mock_response.content = """
    ```json
    {
        "Alaric": {"type": "character", "description": "A brave hero"},
        "Elara": {"type": "character", "description": "A wise healer"},
        "Forest of Shadows": {"type": "location", "description": "A dark ancient forest"}
    }
    ```
    """
    mock_instance.invoke.return_value = mock_response

    # Setup: Initial state with novel text
    initial_state: PipelineState = {
        "novel_text": "Hero Alaric entered the ancient Forest of Shadows, holding his Silver Sword. Beside him stood the wise healer Elara.",
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
    
    # Act: Run the lore_master node
    new_state = lore_master(initial_state)
    
    # Assert
    assert "Alaric" in new_state["entity_graph"]
    assert "Elara" in new_state["entity_graph"]
    assert "Forest of Shadows" in new_state["entity_graph"]
    assert new_state["entity_graph"]["Alaric"].attributes["type"] == "character"
    assert new_state["entity_graph"]["Forest of Shadows"].attributes["type"] == "location"
