import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.pipeline.state import PipelineState
from src.agents.video_qa import video_qa_node

def test_video_qa_pass():
    # Setup mock LLM provider
    mock_provider = MagicMock()
    mock_provider.generate_structured.return_value = {
        "is_pass": True,
        "reasoning": "The video is smooth and accurate.",
        "failure_details": None
    }

    # Setup: Initial state
    shot = {
        "shot_id": "shot_1",
        "scene_id": "scene_1",
        "visual_payload": {"prompt": "A man in the forest"},
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
        "art_style_spec": None,
        "current_keyframe_url": "/tmp/test_project/production/scene_1/shot_1/keyframe_begin.png",
        "image_retry_count": 0,
        "image_qa_feedback": None,
        "current_video_candidate_url": "/tmp/test_project/production/scene_1/shot_1/video.mp4",
        "video_retry_count": 0,
        "video_qa_feedback": None,
        "physics_downgrade_required": False,
        "style_redefinition_required": False,
        "approved_video_assets": [],
        "final_video_path": None,
        "last_error": None
    }
    
    with patch("src.agents.video_qa.get_llm_provider", return_value=mock_provider), \
         patch("src.agents.video_qa.get_production_shot_path", return_value=Path("/tmp/test_project/production/scene_1/shot_1")), \
         patch("src.agents.video_qa.save_agent_metadata"):
        
        # Act
        new_state = video_qa_node(initial_state)
    
    # Assert
    assert new_state["video_qa_feedback"] is None
    assert len(new_state["approved_video_assets"]) == 1
    assert new_state["approved_video_assets"][0] == "/tmp/test_project/production/scene_1/shot_1/video.mp4"
