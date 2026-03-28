import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.pipeline.state import PipelineState
from src.agents.storyboarder import storyboarder

def test_storyboarder_generates_keyframes():
    # Setup mock Image provider
    mock_image_provider = MagicMock()
    mock_image_provider.generate_image.return_value = MagicMock(image_bytes=b"fake_image_bytes")

    # Setup: Initial state
    shot = {
        "shot_id": "shot_1",
        "scene_id": "scene_1",
        "visual_payload": {"prompt": "A man in the forest"},
        "camera_payload": {"movement": "static"},
        "qa_checklist": []
    }
    
    initial_state: PipelineState = {
        "project_dir": "/tmp/test_project",
        "style": "anime",
        "config": {},
        "novel_text": "...",
        "current_chapter_id": "test",
        "l3_graph_mutations": [],
        "scene_ir_blocks": [],
        "current_scene_index": 0,
        "shot_list_ast": [shot],
        "current_shot_index": 0,
        "art_style_spec": {"palette": {"primary": "blue", "lighting_mood": "dark"}},
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
    
    # Mocking paths and utilities
    with patch("src.agents.storyboarder.get_image_provider", return_value=mock_image_provider), \
         patch("src.agents.storyboarder.get_production_scene_path", return_value=Path("/tmp/test_project/production/scene_1")), \
         patch("src.agents.storyboarder.get_production_shot_path", side_effect=lambda state, sid, shid, *args: Path(f"/tmp/test_project/production/{sid}/{shid}").joinpath(*args) if args else Path(f"/tmp/test_project/production/{sid}/{shid}")), \
         patch("src.agents.storyboarder.save_agent_metadata"), \
         patch("src.agents.storyboarder.pack_images"), \
         patch("pathlib.Path.write_bytes"):
        
        # Act
        new_state = storyboarder(initial_state)
    
    # Assert
    assert "current_keyframe_url" in new_state
    assert new_state["current_keyframe_url"] == "/tmp/test_project/production/scene_1/shot_1/keyframe_begin.png"
    assert mock_image_provider.generate_image.call_count == 2
