from pathlib import Path
from src.core.state import PipelineState
from src.agents.utils import get_llm_provider, get_image_provider
from src.providers.base import ImageGenerationConfig
from src.agents.prompts import STORYBOARDER_SYSTEM_PROMPT


def get_video_dimensions(config: dict) -> tuple[int, int]:
    video_cfg = config.get("video", {})
    resolution = video_cfg.get("resolution", "1080p")

    resolution_map = {
        "720p": (1280, 720),
        "1080p": (1920, 1080),
        "4k": (3840, 2160),
        "1:1": (1024, 1024),
        "16:9": (1920, 1080),
        "9:16": (1080, 1920),
    }

    return resolution_map.get(resolution, (1920, 1080))


def storyboarder(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- STORYBOARDER: Generating Keyframes for Shot {shot.id} ---")

    project_dir = state.get("project_dir", "./workspace")

    try:
        config = state.get("config")
        if config:
            models = config.get("models", {})
            agent_cfg = config.get("agents", {}).get("storyboarder", {})
            llm_model_name = agent_cfg.get("model")
            image_model_name = agent_cfg.get("image_model")

            if llm_model_name and image_model_name:
                from src.providers.factory import ProviderFactory

                llm_cfg = models.get(llm_model_name, {})
                image_cfg = models.get(image_model_name, {})
                llm = ProviderFactory.create_llm(llm_cfg)
                image_gen = ProviderFactory.create_image(image_cfg)
            else:
                llm = get_llm_provider(state, "director")
                image_gen = get_image_provider(state, "storyboarder")
        else:
            llm = get_llm_provider(state, "director")
            image_gen = get_image_provider(state, "storyboarder")

        shot_dir = Path(project_dir) / "scenes" / shot.scene_id / "shots" / shot.id
        shot_dir.mkdir(parents=True, exist_ok=True)

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

        state["shot_list"][idx].optimized_prompt = optimized_prompt

        width, height = get_video_dimensions(config) if config else (1920, 1080)
        print(f"  Using video dimensions: {width}x{height}")
        gen_config = ImageGenerationConfig(width=width, height=height, num_images=1)

        print("  Generating begin keyframe...")
        response_begin = image_gen.generate_image(optimized_prompt, gen_config)
        filepath_begin = shot_dir / "keyframe_begin.png"
        filepath_begin.write_bytes(response_begin.image_bytes)
        state["shot_list"][idx].keyframe_begin_url = str(filepath_begin)
        print(f"  Saved begin keyframe: {filepath_begin}")

        end_frame_prompt = f"{optimized_prompt}, end of motion, final pose"
        print("  Generating end keyframe...")
        response_end = image_gen.generate_image(end_frame_prompt, gen_config)
        filepath_end = shot_dir / "keyframe_end.png"
        filepath_end.write_bytes(response_end.image_bytes)
        state["shot_list"][idx].keyframe_end_url = str(filepath_end)
        print(f"  Saved end keyframe: {filepath_end}")

        state["shot_list"][idx].status = "storyboarded"
    except Exception as e:
        print(f"Error in storyboarder: {e}")
        state["last_error"] = str(e)

    return state
