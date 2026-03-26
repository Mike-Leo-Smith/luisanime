import os
import subprocess

import ffmpeg

from src.config import load_config
from src.core.state import PipelineState


def _run_musetalk(input_path: str, output_path: str, device: str) -> None:
    cmd = [
        "python",
        "-m",
        "musetalk.inference",
        "--input",
        input_path,
        "--output",
        output_path,
        "--device",
        device,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def lip_sync_agent(state: PipelineState) -> PipelineState:
    print("--- LIP-SYNC: Applying local mouth masking (MuseTalk) ---")

    config = load_config()
    device: str = config.post_processing.lip_sync.get("device", "cpu")

    synced: list[str] = []
    for clip_path in state["approved_clips"]:
        clip_dir = os.path.dirname(clip_path)
        base = os.path.basename(clip_path)
        output_path = os.path.join(clip_dir, f"sync_{base}")

        try:
            _run_musetalk(clip_path, output_path, device)
            print(f"  [musetalk] {clip_path} -> {output_path}")
            synced.append(output_path)
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
            print(f"  [lip_sync WARNING] MuseTalk failed for {clip_path}: {exc!r}")
            print(f"  [lip_sync WARNING] Falling back to original clip.")
            synced.append(clip_path)

    state["synced_clips"] = synced
    return state


def compositor(state: PipelineState) -> PipelineState:
    print("--- COMPOSITOR: Final Stitching ---")

    clips = state.get("synced_clips") or state.get("approved_clips", [])
    if not clips:
        print("  No clips to composite.")
        state["final_video_path"] = None
        return state

    project_dir = state.get("project_dir", "./workspace")
    os.makedirs(project_dir, exist_ok=True)
    output_path = os.path.join(project_dir, "final_output.mp4")

    try:
        inputs = [ffmpeg.input(c) for c in clips]
        concat_node = ffmpeg.concat(*inputs, v=1, a=0)
        ffmpeg.output(concat_node, output_path).overwrite_output().run(quiet=True)
        print(f"  Composited {len(clips)} clip(s) -> {output_path}")
        state["final_video_path"] = output_path
    except ffmpeg.Error as exc:
        stderr = (
            exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        )
        print(f"  [compositor ERROR] ffmpeg failed: {stderr}")
        state["final_video_path"] = None

    return state
