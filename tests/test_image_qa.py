import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.pipeline.state import PipelineState
from src.agents.image_qa import image_qa_node

def test_image_qa_pass():
    # Setup mock LLM provider
    mock_provider = MagicMock()
    mock_provider.generate_structured.return_value = {
        "is_pass": True,
        "reasoning": "The image matches the prompt.",
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
        "current_video_candidate_url": None,
        "video_retry_count": 0,
        "video_qa_feedback": None,
        "physics_downgrade_required": False,
        "style_redefinition_required": False,
        "approved_video_assets": [],
        "final_video_path": None,
        "last_error": None
    }
    
    with patch("src.agents.image_qa.get_llm_provider", return_value=mock_provider), \
         patch("src.agents.image_qa.get_production_shot_path", return_value=Path("/tmp/test_project/production/scene_1/shot_1")), \
         patch("src.agents.image_qa.save_agent_metadata"):
        
        # Act
        new_state = image_qa_node(initial_state)
    
    # Assert
    assert new_state["image_qa_feedback"] is None
    assert new_state["image_retry_count"] == 0

def test_image_qa_fail():
    # Setup mock LLM provider
    mock_provider = MagicMock()
    mock_provider.generate_structured.return_value = {
        "is_pass": False,
        "reasoning": "The man has 6 fingers.",
        "failure_details": {
            "failure_reason": "Topological error: 6 fingers.",
            "mitigation_suggestion": "Retry with focus on hand detail."
        }
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
        "image_retry_count": 1,
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
    
    with patch("src.agents.image_qa.get_llm_provider", return_value=mock_provider), \
         patch("src.agents.image_qa.get_production_shot_path", return_value=Path("/tmp/test_project/production/scene_1/shot_1")), \
         patch("src.agents.image_qa.save_agent_metadata"):
        
        # Act
        new_state = image_qa_node(initial_state)
    
    # Assert
    assert new_state["image_qa_feedback"] == "Retry with focus on hand detail."
    assert new_state["image_retry_count"] == 2
