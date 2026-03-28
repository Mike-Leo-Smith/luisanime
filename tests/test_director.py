import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.pipeline.state import PipelineState
from src.agents.director import director

def test_director_generates_shot_list():
    # Setup mock LLM provider
    mock_provider = MagicMock()
    mock_provider.generate_structured.return_value = {
        "shots": [
            {
                "shot_id": "shot_1",
                "visual_payload": {"prompt": "Wide shot of Alaric in the forest."},
                "camera_payload": {"movement": "static"},
                "qa_checklist": ["Alaric is visible", "Forest is dark"]
            },
            {
                "shot_id": "shot_2",
                "visual_payload": {"prompt": "Close-up of Alaric's face."},
                "camera_payload": {"movement": "zoom in"},
                "qa_checklist": ["Alaric's eyes are clear"]
            }
        ]
    }

    # Setup: Initial state with one scene block
    scene = {
        "scene_id": "scene_1",
        "location": "Forest of Shadows",
        "time_of_day": "Dusk",
        "characters": ["Alaric"],
        "environment": {"location": "Forest", "atmosphere": "dark"},
        "physical_actions": ["Alaric enters the forest."]
    }
    
    initial_state: PipelineState = {
        "project_dir": "/tmp/test_project",
        "style": "anime",
        "config": {},
        "novel_text": "...",
        "current_chapter_id": "test",
        "l3_graph_mutations": [],
        "scene_ir_blocks": [scene],
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
    
    with patch("src.agents.director.get_llm_provider", return_value=mock_provider), \
         patch("src.agents.director.get_runtime_path", return_value=Path("/tmp/test_project/runtime/shot_list.json")):
        
        # Act
        new_state = director(initial_state)
    
    # Assert
    assert len(new_state["shot_list_ast"]) == 2
    assert new_state["shot_list_ast"][0]["shot_id"] == "scene_1_shot_1"
    assert new_state["shot_list_ast"][1]["camera_payload"]["movement"] == "zoom in"
    assert new_state["current_shot_index"] == 0
