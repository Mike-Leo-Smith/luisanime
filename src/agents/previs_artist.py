from typing import Dict, Any, List, Optional
import time
from src.agents.base import BaseExecutor
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.providers.base import VideoGenerationConfig
from src.agents.prompts import PREVIS_ARTIST_PROMPT


class PrevisArtistAgent(BaseExecutor):
    def generate_proxy_video(self, plan: ShotExecutionPlan) -> str:
        print(f"🦴 [Pre-vis Artist] Generating proxy video for: {plan.shot_id}")
        print(
            f"   Camera: {plan.camera_movement} | Duration: {plan.target_duration_ms}ms"
        )

        try:
            master_style = self.workspace.read_file("03_lore_bible/master_style.md")
        except:
            master_style = "Cinematic, high fidelity."

        prompt = f"Master Style: {master_style}. Structural proxy video focusing on blocking and motion: {plan.camera_movement}. Action: {plan.action_description}. Entities: {plan.active_entities}. Low fidelity, skeletal motion."

        config = VideoGenerationConfig(
            duration=max(2, plan.target_duration_ms // 1000), resolution="720p"
        )

        video_path = f"05_dailies/{plan.shot_id}/proxy.mp4"
        self.log_prompt(
            "PrevisArtist", plan.shot_id, prompt, custom_path=f"{video_path}.prompt.txt"
        )

        print(f"🦴 [Pre-vis Artist] Calling video API...")
        t0 = time.time()
        response = self.video_gen.generate_video(prompt=prompt, config=config)
        elapsed = time.time() - t0

        self.workspace.save_media(video_path, response.video_bytes)
        print(
            f"🦴 [Pre-vis Artist] Proxy video saved: {video_path} ({len(response.video_bytes)} bytes, {elapsed:.1f}s)"
        )
        return video_path


def previs_artist_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"🦴 [Pre-vis Artist] === NODE ENTRY ===")
    plan = state.get("active_shot_plan")
    print(f"   active_shot_plan: {plan.shot_id if plan else None}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = PrevisArtistAgent.from_config(ws, state["project_config"])

    plan = state["active_shot_plan"]
    proxy_path = agent.generate_proxy_video(plan)

    print(f"🦴 [Pre-vis Artist] === NODE EXIT === proxy={proxy_path}")
    return {"current_proxy_path": proxy_path, "continuity_feedback": None}
