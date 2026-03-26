from pathlib import Path
from src.core.state import PipelineState
from src.agents.utils import get_llm_provider, get_image_provider
from src.providers.base import ImageGenerationConfig
from src.agents.prompts import STORYBOARDER_SYSTEM_PROMPT
from src.config import load_config, ConfigLoader
from src.providers.factory import ProviderFactory


def storyboarder(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- STORYBOARDER: Generating Keyframe for Shot {shot.id} ---")

    project_dir = state.get("project_dir", "./workspace")

    try:
        config = load_config(Path(project_dir) if project_dir else None)
        models = config.get("models", {})
        agent_cfg = ConfigLoader.get_agent_config(config, "storyboarder")

        llm_model_name = agent_cfg.get("llm_model")
        image_model_name = agent_cfg.get("image_model")

        if not llm_model_name or not image_model_name:
            raise ValueError(
                "storyboarder config must specify both 'llm_model' and 'image_model'. "
                f"Got llm_model={llm_model_name}, image_model={image_model_name}"
            )

        llm_cfg = models.get(llm_model_name, {})
        image_cfg = models.get(image_model_name, {})

        llm = ProviderFactory.create_llm(llm_cfg)
        image_gen = ProviderFactory.create_image(image_cfg)

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
