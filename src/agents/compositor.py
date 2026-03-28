import os
import ffmpeg
from pathlib import Path
from typing import Dict
from src.pipeline.state import PipelineState

def compositor(state: PipelineState) -> Dict:
    print("🎬 [Compositor] Final Stitching of approved clips...")
    
    clips = state.get("approved_video_assets", [])
    if not clips:
        print("  No approved clips to composite.")
        return {"last_error": "No approved clips"}

    project_dir = state.get("project_dir", "./workspace")
    output_dir = Path(project_dir) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "final_video.mp4"

    try:
        inputs = [ffmpeg.input(c) for c in clips]
        concat_node = ffmpeg.concat(*inputs, v=1, a=0)
        ffmpeg.output(concat_node, str(output_path)).overwrite_output().run(quiet=True)
        print(f"  ✅ Composited {len(clips)} clip(s) -> {output_path}")
        return {"final_video_path": str(output_path)}
    except Exception as e:
        print(f"  [Compositor ERROR] {e}")
        return {"last_error": str(e)}

def lip_sync_agent(state: PipelineState) -> Dict:
    return {}
