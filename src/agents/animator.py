from pathlib import Path
from src.core.state import PipelineState
from src.agents.utils import get_video_provider
from src.providers.base import VideoGenerationConfig


def animator(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- ANIMATOR: Generating Video for Shot {shot.id} ---")

    project_dir = state.get("project_dir", "./workspace")

    try:
        if not shot.keyframe_url:
            raise ValueError(f"Shot {shot.id} is missing a keyframe.")

        provider = get_video_provider(state, "animator")
        gen_config = VideoGenerationConfig(duration=6, resolution="1080p")

        print(f"  Generating video for: {shot.prompt[:60]}...")
        response = provider.generate_video(shot.prompt, shot.keyframe_url, gen_config)

        if not response.video_bytes:
            raise ValueError("Video generation returned empty bytes")

        shot_dir = Path(project_dir) / "scenes" / shot.scene_id / "shots" / shot.id
        shot_dir.mkdir(parents=True, exist_ok=True)

        video_path = shot_dir / "video.mp4"
        video_path.write_bytes(response.video_bytes)

        state["shot_list"][idx].video_url = str(video_path)
        state["shot_list"][idx].status = "animated"
        print(f"  Saved video: {video_path}")
    except Exception as e:
        print(f"Error in animator: {e}")
        state["last_error"] = str(e)

    return state
