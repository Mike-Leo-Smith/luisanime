import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from PIL import Image
import time
import functools
import subprocess

from src.pipeline.state import AFCState
from src.config import load_config, ConfigLoader
from src.providers.factory import ProviderFactory


def get_llm_provider(state: AFCState, agent_name: str):
    config = load_config(Path(state["workspace_root"]))
    model_cfg = ConfigLoader.get_agent_config(config, agent_name)
    return ProviderFactory.create_llm(model_cfg)


def get_image_provider(state: AFCState, agent_name: str):
    config = load_config(Path(state["workspace_root"]))
    model_cfg = ConfigLoader.get_agent_config(config, agent_name)
    return ProviderFactory.create_image(model_cfg)


def get_video_provider(state: AFCState, agent_name: str):
    config = load_config(Path(state["workspace_root"]))
    model_cfg = ConfigLoader.get_agent_config(config, agent_name)
    return ProviderFactory.create_video(model_cfg)


def get_workspace_path(state: AFCState, *args) -> Path:
    path = Path(state["workspace_root"]).joinpath(*args)
    path.mkdir(parents=True, exist_ok=True)
    return path


def pack_images(
    image_paths: List[Union[str, Path]], output_path: Path, grid_cols: int = 2
):
    if not image_paths:
        return

    images = [Image.open(p) for p in image_paths]
    base_w, base_h = images[0].size
    images = [img.resize((base_w, base_h)) for img in images]

    rows = (len(images) + grid_cols - 1) // grid_cols
    canvas = Image.new("RGB", (base_w * grid_cols, base_h * rows))

    for i, img in enumerate(images):
        x = (i % grid_cols) * base_w
        y = (i // grid_cols) * base_h
        canvas.paste(img, (x, y))

    canvas.save(output_path)
    print(f"  [Utils] Packed {len(images)} images into {output_path}")


def retry_with_backoff(retries=3, backoff_in_seconds=2, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if x == retries:
                        raise e
                    wait = backoff_in_seconds * 2**x
                    print(
                        f"  [Retry] Attempt {x + 1} failed: {e}. Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                    x += 1

        return wrapper

    return decorator


def save_agent_metadata(path: Path, metadata: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def sample_frames(
    video_path: Path, output_dir: Path, num_frames: int = 3
) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_paths = []

    cmd_dur = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        duration = float(subprocess.check_output(cmd_dur).decode().strip())
    except Exception:
        duration = 5.0

    for i in range(num_frames):
        timestamp = (duration / (num_frames + 1)) * (i + 1)
        out_path = output_dir / f"sample_{i}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(timestamp),
            "-i",
            str(video_path),
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(out_path),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if out_path.exists():
            frame_paths.append(out_path)

    return frame_paths
