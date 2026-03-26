import os
import uuid
from pathlib import Path
from typing import Any
from src.core.state import PipelineState
from src.agents.utils import get_image_provider
from src.providers.base import ImageGenerationConfig


def storyboarder(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- STORYBOARDER: Generating Keyframe for Shot {shot.id} ---")

    project_dir = state.get("project_dir", "./workspace")

    try:
        provider = get_image_provider(state, "storyboarder")
        gen_config = ImageGenerationConfig(width=1024, height=1024, num_images=1)

        print(f"  Generating image for: {shot.prompt[:60]}...")
        response = provider.generate_image(shot.prompt, gen_config)

        # Save to proper project structure: scenes/{scene_id}/shots/{shot_id}/
        shot_dir = Path(project_dir) / "scenes" / shot.scene_id / "shots" / shot.id
        shot_dir.mkdir(parents=True, exist_ok=True)

        filepath = shot_dir / "keyframe.png"
        filepath.write_bytes(response.image_bytes)

        state["shot_list"][idx].keyframe_url = str(filepath)
        state["shot_list"][idx].status = "storyboarded"
        print(f"  Saved keyframe: {filepath}")
    except Exception as e:
        print(f"Error in storyboarder: {e}")
        state["last_error"] = str(e)

    return state
