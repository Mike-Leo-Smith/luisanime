from typing import Dict, Any, List, Optional
from src.agents.base import BaseExecutor
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.providers.base import VideoGenerationConfig
from src.agents.prompts import LEAD_ANIMATOR_PROMPT

class LeadAnimatorAgent(BaseExecutor):
    def generate_video_v2v(self, plan: ShotExecutionPlan, keyframe: str, proxy: Optional[str], prompt: str) -> str:
        """Invokes the external generative video API (e.g., MiniMax)."""
        shot_id = plan.shot_id
        print(f"🎨 [Lead Animator] Executing render for {shot_id}...")
        
        try:
            master_style = self.workspace.read_file("03_lore_bible/master_style.md")
        except:
            master_style = "Cinematic, high fidelity."

        # GENERIC ARCHITECTURAL SOLUTION FOR API SAFETY:
        # Distill EVERYTHING (Action, Style, Camera) into a single, safe English motion prompt.
        distillation_prompt = f"""Combine the following cinematic instructions into a single PURELY PHYSICAL motion description in English for a video model.
        STRICT RULE: Remove all character names, specific locations, brand names, and sensitive/abstract concepts.
        Focus ONLY on: light quality, camera movement, and physical body dynamics.
        
        Style Guide: {master_style}
        Action: {prompt}
        Camera Plan: {plan.detailed_camera_plan}
        
        Output ONLY the distilled English description."""
        
        distilled_resp = self.llm.generate_text(distillation_prompt, system_prompt=LEAD_ANIMATOR_PROMPT)
        safe_prompt = distilled_resp.text.strip()
        
        style_key = self.project_config.get("video", {}).get("style", "cinematic")
        preset = self.project_config.get("style_presets", {}).get(style_key, {})
        prefix = preset.get("prompt_prefix", "")
        suffix = preset.get("prompt_suffix", "")

        # Final prompt is now purely distilled safety-safe English
        full_prompt = f"{prefix} {safe_prompt} {suffix}"
        
        config = VideoGenerationConfig()
        if proxy:
            config.control_video_path = self.workspace.get_physical_path(proxy)
        
        video_path = f"05_dailies/{shot_id}/render.mp4"
        self.log_prompt("LeadAnimator", shot_id, full_prompt, custom_path=f"{video_path}.prompt.txt")
        
        response = self.video_gen.generate_video(
            prompt=full_prompt, 
            image_path=self.workspace.get_physical_path(keyframe),
            config=config
        )
        
        self.workspace.save_media(video_path, response.video_bytes)
        print(f"🎨 [Lead Animator] Render complete: {video_path}")
        return video_path

def lead_animator_node(state: AFCState) -> Dict:
    from src.pipeline.workspace import AgenticWorkspace
    ws = AgenticWorkspace(state["workspace_root"])
    agent = LeadAnimatorAgent.from_config(ws, state["project_config"])
    
    plan = state["active_shot_plan"]
    if not plan:
        return {}
        
    render_path = agent.generate_video_v2v(
        plan,
        state["current_keyframe_path"],
        state.get("current_proxy_path"),
        plan.action_description
    )
    
    return {
        "current_render_path": render_path
    }
