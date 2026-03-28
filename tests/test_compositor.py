import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.pipeline.state import PipelineState
from src.agents.compositor import compositor

def test_compositor_stitches_videos():
    # Setup: Initial state
    approved_clips = ["clip1.mp4", "clip2.mp4"]
    
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
        "approved_video_assets": approved_clips,
        "final_video_path": None,
        "last_error": None
    }
    
    # Mocking ffmpeg
    with patch("ffmpeg.input") as mock_input, \
         patch("ffmpeg.concat") as mock_concat, \
         patch("ffmpeg.output") as mock_output:
        
        mock_output.return_value.overwrite_output.return_value.run.return_value = None
        
        # Act
        new_state = compositor(initial_state)
    
    # Assert
    assert "final_video_path" in new_state
    assert new_state["final_video_path"] == "/tmp/test_project/output/final_video.mp4"
    assert mock_input.call_count == 2
    assert mock_concat.called
    assert mock_output.called
