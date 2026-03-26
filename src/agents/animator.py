from pathlib import Path
from typing import Any
from src.core.state import PipelineState
from src.agents.utils import get_video_provider
from src.providers.base import VideoGenerationConfig


def generate_video_clip(prompt: str, keyframe_path: str, config: Any) -> bytes:
    print(f"--- VIDEO GEN: {prompt[:60]}... ---")

    provider = get_video_provider(config, "animator")
    gen_config = VideoGenerationConfig(duration=6, resolution="1080p")
    response = provider.generate_video(prompt, keyframe_path, gen_config)

    return response.video_bytes


def animator(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- ANIMATOR: Generating Video for Shot {shot.id} ---")

    project_dir = state.get("project_dir", "./workspace")

    try:
        if not shot.keyframe_url:
            raise ValueError(f"Shot {shot.id} is missing a keyframe.")

        video_bytes = generate_video_clip(shot.prompt, shot.keyframe_url, state)

        if not video_bytes:
            raise ValueError("Video generation returned empty bytes")

        video_path = f"{project_dir}/scenes/{shot.id}_video.mp4"
        with open(video_path, "wb") as f:
            f.write(video_bytes)

        state["shot_list"][idx].video_url = video_path
        state["shot_list"][idx].status = "animated"
        print(f"  Saved video: {video_path}")
    except Exception as e:
        print(f"Error in animator: {e}")
        state["last_error"] = str(e)

    return state
