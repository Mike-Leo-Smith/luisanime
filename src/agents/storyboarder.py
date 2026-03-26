from pathlib import Path
from src.core.state import PipelineState
from src.agents.utils import get_image_provider, get_llm_provider
from src.providers.base import ImageGenerationConfig
from src.agents.prompts import STORYBOARDER_SYSTEM_PROMPT


def storyboarder(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- STORYBOARDER: Generating Keyframe for Shot {shot.id} ---")

    project_dir = state.get("project_dir", "./workspace")

    try:
        llm = get_llm_provider(state, "storyboarder")
        image_gen = get_image_provider(state, "storyboarder")

        optimization_prompt = f"""{STORYBOARDER_SYSTEM_PROMPT}

Director's visual description:
{shot.prompt}

Camera: {shot.camera_movement}
Duration: {shot.duration}s
Style: {state.get("style", "anime")}

Optimize this into a dense, high-quality image generation prompt."""

        print("  Optimizing prompt...")
        optimized_response = llm.generate_text(optimization_prompt)
        optimized_prompt = optimized_response.text.strip()
        print(f"  Optimized: {optimized_prompt[:80]}...")

        # Step 2: Generate image with optimized prompt
        gen_config = ImageGenerationConfig(width=1024, height=1024, num_images=1)
        response = image_gen.generate_image(optimized_prompt, gen_config)

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
