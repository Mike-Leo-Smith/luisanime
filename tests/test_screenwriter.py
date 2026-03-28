import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.pipeline.state import PipelineState
from src.agents.screenwriter import screenwriter

def test_screenwriter_chunks_scenes():
    # Setup mock LLM provider
    mock_provider = MagicMock()
    mock_provider.generate_structured.return_value = {
        "scenes": [
            {
                "scene_id": "scene_1",
                "location": "Forest of Shadows",
                "time_of_day": "Dusk",
                "characters": ["Alaric", "Elara"],
                "environment": {"location": "Forest", "atmosphere": "dark"},
                "physical_actions": ["Alaric and Elara enter the forest."]
            },
            {
                "scene_id": "scene_2",
                "location": "Ancient Temple",
                "time_of_day": "Night",
                "characters": ["Alaric"],
                "environment": {"location": "Temple", "atmosphere": "eerie"},
                "physical_actions": ["Alaric finds a temple."]
            }
        ]
    }

    # Mock ChapterDB
    mock_chapter = MagicMock()
    mock_chapter.id = "chapter_001"
    mock_chapter.text = "Raw prose about a forest..."
    
    mock_db = MagicMock()
    mock_db.get_all_chapters.return_value = [mock_chapter]

    # Setup: Initial state
    initial_state: PipelineState = {
        "project_dir": "/tmp/test_project",
        "style": "anime",
        "config": {},
        "novel_text": "...",
        "current_chapter_id": "test",
        "l3_graph_mutations": [],
        "scene_ir_blocks": [],
        "current_scene_index": 0,
        "shot_list_ast": [],
        "current_shot_index": 0,
        "art_style_spec": None,
        "current_keyframe_url": None,
        "image_retry_count": 0,
        "image_qa_feedback": None,
        "current_video_candidate_url": None,
        "video_retry_count": 0,
        "video_qa_feedback": None,
        "physics_downgrade_required": False,
        "style_redefinition_required": False,
        "approved_video_assets": [],
        "final_video_path": None,
        "last_error": None
    }
    
    with patch("src.agents.screenwriter.get_llm_provider", return_value=mock_provider), \
         patch("src.agents.screenwriter.get_chapter_db", return_value=mock_db), \
         patch("src.agents.screenwriter.get_runtime_path", return_value=Path("/tmp/test_project/runtime/screenplay/scenes.json")):
        
        # Act
        new_state = screenwriter(initial_state)
    
    # Assert
    assert len(new_state["scene_ir_blocks"]) == 2
    assert new_state["scene_ir_blocks"][0]["scene_id"] == "chapter_001_scene_1"
    assert new_state["scene_ir_blocks"][1]["location"] == "Ancient Temple"
    assert "Alaric" in new_state["scene_ir_blocks"][0]["characters"]
