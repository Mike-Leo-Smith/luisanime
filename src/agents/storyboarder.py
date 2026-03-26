import os
import uuid
from pathlib import Path
from typing import Any
from src.core.state import PipelineState
from src.agents.utils import get_image_provider
from src.providers.base import ImageGenerationConfig


def generate_image_keyframe(prompt: str, config: Any, project_dir: str) -> str:
    print(f"--- IMAGE GEN (MiniMax): {prompt[:60]}... ---")

    provider = get_image_provider(config, "storyboarder")
    gen_config = ImageGenerationConfig(width=1024, height=1024, num_images=1)
    response = provider.generate_image(prompt, gen_config)

    filename = f"keyframe_{uuid.uuid4().hex[:8]}.png"
    shots_dir = os.path.join(project_dir, "scenes")
    os.makedirs(shots_dir, exist_ok=True)
    filepath = os.path.join(shots_dir, filename)

    with open(filepath, "wb") as f:
        f.write(response.image_bytes)

    return filepath


def storyboarder(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- STORYBOARDER: Generating Keyframe for Shot {shot.id} ---")

    project_dir = state.get("project_dir", "./workspace")

    try:
        filepath = generate_image_keyframe(shot.prompt, state, project_dir)
        state["shot_list"][idx].keyframe_url = filepath
        state["shot_list"][idx].status = "storyboarded"
        print(f"  Saved keyframe: {filepath}")
    except Exception as e:
        print(f"Error in storyboarder: {e}")
        state["last_error"] = str(e)

    return state
