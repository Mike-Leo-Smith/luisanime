import pytest
from unittest.mock import MagicMock, patch
from src.core.state import PipelineState, Shot
from src.core.graph import storyboarder

@patch("src.core.graph.ChatGoogleGenerativeAI")
def test_storyboarder_generates_keyframe(mock_llm):
    # For Storyboarder, we need to mock whatever image API we use.
    # If we use a LangChain-compatible image model or a custom wrapper.
    # Let's assume for now we use a custom utility or the same Gemini 
    # model to "describe" the image and a mock image generator.
    
    # Let's mock a hypothetical Image API call
    with patch("src.core.graph.load_config") as mock_config_load:
        mock_cfg = MagicMock()
        mock_cfg.render_plane.storyboarder.api_key = "fake_key"
        mock_config_load.return_value = mock_cfg
        
        # Mocking a hypothetical image generation function in src.utils
        # or assuming the node does it directly.
        # For now, let's mock the internal implementation detail or just the 
        # expected outcome if we use a specific library.
        
        initial_shot = Shot(
            id="shot_1_1",
            scene_id="scene_1",
            prompt="A man in the forest",
            camera_movement="Static",
            duration=3.0
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
        
        # Mocking the actual image generation (e.g., Nano Banana 2 via Google API)
        # We'll need a real implementation in graph.py
        with patch("src.core.graph.generate_image_keyframe") as mock_gen:
            mock_gen.return_value = "https://example.com/keyframe.jpg"
            
            # Act
            new_state = storyboarder(initial_state)
            
            # Assert
            assert new_state["shot_list"][0].keyframe_url == "https://example.com/keyframe.jpg"
            assert new_state["shot_list"][0].status == "storyboarded"
