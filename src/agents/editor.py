from typing import Dict, Any, List, Optional
import ffmpeg
from src.agents.base import BaseCompiler
from src.pipeline.state import AFCState


class EditorAgent(BaseCompiler):
    def _probe_duration(self, physical_path: str) -> float:
        try:
            probe = ffmpeg.probe(physical_path)
            return float(probe["format"]["duration"])
        except Exception:
            return 5.0

    def mux_scene(self, shot_paths: List[str], scene_id: str) -> str:
        """Executes the FFMPEG build and outputs the master file."""
        print(f"✂️ [Editor] Muxing {len(shot_paths)} shots for scene {scene_id}...")
        if not shot_paths:
            print("✂️ [Editor] WARNING: No shots to mux.")
            return ""

        output_path = self.workspace.get_physical_path(
            f"05_dailies/{scene_id}_master.mp4"
        )

        has_audio = []
        for p in shot_paths:
            phys = self.workspace.get_physical_path(p)
            try:
                probe = ffmpeg.probe(phys)
                audio_streams = [
                    s for s in probe.get("streams", []) if s["codec_type"] == "audio"
                ]
                has_audio.append(len(audio_streams) > 0)
            except (ffmpeg.Error, KeyError, Exception):
                has_audio.append(False)

        any_audio = any(has_audio)
        all_audio = all(has_audio)
        print(
            f"✂️ [Editor] Audio probe: {sum(has_audio)}/{len(has_audio)} clips have audio"
        )

        segments = []
        for i, p in enumerate(shot_paths):
            inp = ffmpeg.input(self.workspace.get_physical_path(p))
            vid = (
                inp.video.filter(
                    "scale", 1920, 1080, force_original_aspect_ratio="decrease"
                )
                .filter("pad", 1920, 1080, "(ow-iw)/2", "(oh-ih)/2")
                .filter("setsar", 1)
            )
            segments.append(vid)

            if any_audio:
                if has_audio[i]:
                    segments.append(
                        inp.audio.filter("loudnorm", I=-16, TP=-1.5, LRA=11)
                    )
                else:
                    silent = ffmpeg.input(
                        "anullsrc=r=44100:cl=stereo",
                        f="lavfi",
                        t=self._probe_duration(self.workspace.get_physical_path(p)),
                    )
                    segments.append(silent)

        try:
            if any_audio:
                (
                    ffmpeg.concat(*segments, v=1, a=1)
                    .output(
                        output_path,
                        vcodec="libx264",
                        acodec="aac",
                        pix_fmt="yuv420p",
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )
                print(f"✂️ [Editor] Scene master created (with audio): {output_path}")
            else:
                (
                    ffmpeg.concat(*segments, v=1, a=0)
                    .output(output_path, vcodec="libx264", pix_fmt="yuv420p")
                    .overwrite_output()
                    .run(quiet=True)
                )
                print(f"✂️ [Editor] Scene master created (no audio): {output_path}")
        except ffmpeg.Error as e:
            stderr_msg = e.stderr.decode() if e.stderr else str(e)
            print(f"✂️ [Editor] FFMPEG Error: {stderr_msg}")
            print(f"✂️ [Editor] Retrying video-only...")
            try:
                vid_only = []
                for p in shot_paths:
                    stream = ffmpeg.input(self.workspace.get_physical_path(p))
                    stream = stream.filter(
                        "scale", 1920, 1080, force_original_aspect_ratio="decrease"
                    )
                    stream = stream.filter("pad", 1920, 1080, "(ow-iw)/2", "(oh-ih)/2")
                    stream = stream.filter("setsar", 1)
                    vid_only.append(stream)
                (
                    ffmpeg.concat(*vid_only, v=1, a=0)
                    .output(output_path, vcodec="libx264", pix_fmt="yuv420p")
                    .overwrite_output()
                    .run(quiet=True)
                )
                print(
                    f"✂️ [Editor] Scene master created (fallback, no audio): {output_path}"
                )
            except ffmpeg.Error as e2:
                stderr_msg2 = e2.stderr.decode() if e2.stderr else str(e2)
                print(f"✂️ [Editor] FFMPEG Retry also failed: {stderr_msg2}")
                print(f"✂️ [Editor] Skipping master creation for {scene_id}")

        return f"05_dailies/{scene_id}_master.mp4"


def editor_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"✂️ [Editor] === NODE ENTRY ===")
    scene_path = state.get("current_scene_path", "")
    dailies = state.get("scene_dailies_paths", [])
    print(f"   current_scene_path: {scene_path}")
    print(f"   scene_dailies_paths: {len(dailies)} clips — {dailies}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = EditorAgent.from_config(ws, state["project_config"])

    if not scene_path:
        print(f"✂️ [Editor] === NODE EXIT === No scene_path — skipping")
        return {}

    scene_id = scene_path.split("/")[-1].replace(".json", "")
    master_path = agent.mux_scene(state.get("scene_dailies_paths", []), scene_id)

    completed = [master_path] if master_path else []

    print(f"✂️ [Editor] === NODE EXIT === master={master_path}")
    print(f"   Clearing scene_dailies_paths, current_scene_path")
    return {
        "completed_scenes_paths": completed,
        "scene_dailies_paths": [],
        "current_scene_path": None,
    }
