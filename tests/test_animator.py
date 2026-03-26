import pytest
from unittest.mock import MagicMock, patch
from src.core.state import PipelineState, Shot
from src.core.graph import animator

def test_animator_generates_video():
    with patch("src.core.graph.load_config") as mock_config_load:
        mock_cfg = MagicMock()
        mock_cfg.render_plane.animator.api_key = "fake_key"
        mock_config_load.return_value = mock_cfg
        
        initial_shot = Shot(
            id="shot_1_1",
            scene_id="scene_1",
            prompt="A man in the forest",
            camera_movement="Static",
            duration=3.0,
            keyframe_url="https://example.com/keyframe.jpg",
            status="storyboarded"
        )
        
        initial_state: PipelineState = {
            "novel_text": "...",
            "current_chapter_id": "ch1",
            "entity_graph": {},
            "scenes": [],
            "current_scene_index": 0,
            "shot_list": [initial_shot],
            "current_shot_index": 0,
            "retry_count": 0,
            "last_error": None,
            "approved_clips": []
        }
        
        # Mocking the actual video generation (e.g., Veo via Hailuo/Google)
        with patch("src.core.graph.generate_video_clip") as mock_gen:
            mock_gen.return_value = "https://example.com/shot_1_1.mp4"
            
            # Act
            new_state = animator(initial_state)
            
            # Assert
            assert new_state["shot_list"][0].video_url == "https://example.com/shot_1_1.mp4"
            assert new_state["shot_list"][0].status == "animated"
