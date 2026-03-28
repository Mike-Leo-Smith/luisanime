import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.pipeline.state import PipelineState
from src.agents.lore_master import lore_master

def test_lore_master_extracts_mutations():
    # Setup mock LLM provider
    mock_provider = MagicMock()
    mock_provider.generate_structured.return_value = {
        "mutations": [
            {
                "entity": "Alaric",
                "mutation": "Lost his shield",
                "permanent": True
            },
            {
                "entity": "Forest",
                "mutation": "Turned dark",
                "permanent": False
            }
        ]
    }

    # Mock ChapterDB
    mock_chapter = MagicMock()
    mock_chapter.id = "chapter_001"
    mock_chapter.text = "Alaric lost his shield in the dark forest."
    
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
    
    with patch("src.agents.lore_master.get_llm_provider", return_value=mock_provider), \
         patch("src.agents.lore_master.get_chapter_db", return_value=mock_db), \
         patch("src.agents.lore_master.get_runtime_path", return_value=Path("/tmp/test_project/runtime/lore/mutations.json")):
        
        # Act
        new_state = lore_master(initial_state)
    
    # Assert
    assert len(new_state["l3_graph_mutations"]) == 2
    assert new_state["l3_graph_mutations"][0]["entity"] == "Alaric"
    assert new_state["l3_graph_mutations"][1]["mutation"] == "Turned dark"
