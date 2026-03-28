from typing import Dict, Any, List, Optional
import json
from src.agents.base import BaseExecutor
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.providers.base import ImageGenerationConfig
from src.agents.prompts import CINEMATOGRAPHER_PROMPT

import ffmpeg
import os

class CinematographerAgent(BaseExecutor):
    def _extract_continuity_frames(self, video_path: str, shot_id: str) -> List[str]:
        """Extracts start, middle, and end frames from a video for continuity."""
        print(f"📸 [Cinematographer] Extracting continuity frames from {video_path}...")
        physical_video = self.workspace.get_physical_path(video_path)
        output_dir = self.workspace.get_physical_path(f"05_dailies/{shot_id}/continuity")
        os.makedirs(output_dir, exist_ok=True)
        
        # Get duration
        try:
            probe = ffmpeg.probe(physical_video)
            duration = float(probe['format']['duration'])
        except:
            return []

        frames = []
        # Extract at 0%, 50%, 95%
        for i, pct in enumerate([0, 0.5, 0.95]):
            out_path = os.path.join(output_dir, f"ref_{i}.png")
            try:
                (
                    ffmpeg
                    .input(physical_video, ss=duration * pct)
                    .filter('scale', 1280, -1)
                    .output(out_path, vframes=1)
                    .overwrite_output()
                    .run(quiet=True)
                )
                frames.append(f"05_dailies/{shot_id}/continuity/ref_{i}.png")
            except:
                pass
        return frames

    def fetch_lore_context(self, entities: List[str]) -> str:
        """Retrieves active physical states from the Lore Bible."""
        print(f"📸 [Cinematographer] Gathering lore for {entities}...")
        context = []
        for entity in entities:
            try:
                lore = self.workspace.read_file(f"03_lore_bible/{entity}.md")
                context.append(lore)
            except:
                pass
        return "\n".join(context)
    
    def fetch_design_references(self, entities: List[str]) -> List[str]:
        """Retrieves locked visual designs (images) for entities."""
        designs = []
        for entity in entities:
            path = f"03_lore_bible/designs/{entity}.png"
            if self.workspace.exists(path):
                designs.append(path)
        return designs
        
    def generate_image_constrained(self, plan: ShotExecutionPlan, lore_context: str, designs: List[str], continuity_refs: List[str], feedback: Optional[str] = None) -> str:
        """Outputs the master keyframe_v1.png using detailed shot plan and references."""
        shot_id = plan.shot_id
        print(f"📸 [Cinematographer] Generating STRICT STARTING FRAME for: {shot_id}...")
        
        try:
            master_style = self.workspace.read_file("03_lore_bible/master_style.md")
        except:
            master_style = "Cinematic, high fidelity."

        video_cfg = self.project_config.get("video", {})
        style_key = video_cfg.get("style", "cinematic")
        preset = self.project_config.get("style_presets", {}).get(style_key, {})
        prefix = preset.get("prompt_prefix", "")
        suffix = preset.get("prompt_suffix", "")

        # CONTINUITY INSTRUCTIONS
        continuity_note = ""
        if continuity_refs:
            continuity_note = "CRITICAL: Maintain ABSOLUTE visual and stylistic consistency with the PREVIOUS SHOT (refer to the attached video frames)."

        # MANDATORY STARTING FRAME INSTRUCTIONS
        full_prompt = f"""{prefix} 
STRICT RULE: This image MUST be the absolute STARTING FRAME (First Frame) of the shot.
STRICT RULE: Generate ONE single focused cinematic shot. NO multi-panels, NO montages.

{continuity_note}

STARTING COMPOSITION (Frame 0):
ACTION START: {plan.action_description}
INITIAL STAGING: {plan.staging_description}
INITIAL POSES: {json.dumps(plan.character_poses, ensure_ascii=False)}

ERA CONTEXT: {plan.era_context}
ATMOSPHERE: {plan.setting_details}

LORE CONTEXT: {lore_context}

VISUAL STYLE REFERENCE:
{master_style}

TECHNICAL: 8k resolution, photorealistic, masterpiece. {suffix}"""
        
        if feedback:
            full_prompt += f"\nREVISION FEEDBACK (FIX THESE): {feedback}"
            
        print(f"📸 [Cinematographer] Final Prompt for {shot_id}:\n{full_prompt[:500]}...")
            
        # Combine design designs and continuity frames
        all_refs = designs + continuity_refs
        physical_refs = [self.workspace.get_physical_path(p) for p in all_refs]
        
        # ENSURE RESOLUTION MATCHES VIDEO
        res_str = video_cfg.get("resolution", "1080p")
        width, height = 1920, 1080
        if res_str == "720p": width, height = 1280, 720
        elif res_str == "4k": width, height = 3840, 2160
        
        image_path = f"05_dailies/{shot_id}/keyframe_v1.png"
        self.log_prompt("Cinematographer", shot_id, full_prompt, custom_path=f"{image_path}.prompt.txt")
        
        config = ImageGenerationConfig(
            width=width,
            height=height,
            reference_media=physical_refs
        )
        response = self.image_gen.generate_image(prompt=full_prompt, config=config)
        
        self.workspace.save_media(image_path, response.image_bytes)
        print(f"📸 [Cinematographer] Starting Frame saved: {image_path}")
        return image_path

def cinematographer_node(state: AFCState) -> Dict:
    from src.pipeline.workspace import AgenticWorkspace
    ws = AgenticWorkspace(state["workspace_root"])
    agent = CinematographerAgent.from_config(ws, state["project_config"])
    
    plan = state.get("active_shot_plan")
    if not plan:
        print("📸 [Cinematographer] WARNING: No active shot plan found in state.")
        return {}
        
    lore = agent.fetch_lore_context(plan.active_entities)
    designs = agent.fetch_design_references(plan.active_entities)
    feedback = state.get("continuity_feedback")
    
    # Identify last approved shot for continuity
    continuity_refs = []
    dailies = state.get("scene_dailies_paths", [])
    if dailies:
        last_video = dailies[-1]
        continuity_refs = agent._extract_continuity_frames(last_video, plan.shot_id)
    
    keyframe_path = agent.generate_image_constrained(
        plan, 
        lore, 
        designs,
        continuity_refs,
        feedback=feedback
    )
    
    # Return path to update state
    return {
        "current_keyframe_path": keyframe_path
    }
