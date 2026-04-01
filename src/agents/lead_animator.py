from typing import Dict, Optional
import os
import time
import ffmpeg
from src.agents.base import BaseExecutor
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.providers.base import VideoGenerationConfig
from src.agents.prompts import LEAD_ANIMATOR_PROMPT


class LeadAnimatorAgent(BaseExecutor):
    def _extract_last_frame(self, video_path: str, output_dir: str) -> Optional[str]:
        physical_video = self.workspace.get_physical_path(video_path)
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, "last_frame.png")

        try:
            probe = ffmpeg.probe(physical_video)
            duration = float(probe["format"]["duration"])
            (
                ffmpeg.input(physical_video, ss=duration * 0.95)
                .filter("scale", 1920, -1)
                .output(out_path, vframes=1)
                .overwrite_output()
                .run(quiet=True)
            )
            return out_path
        except Exception as e:
            print(f"🎨 [Lead Animator] Failed to extract last frame: {e}")
            return None

    def _load_previous_shot_plan(
        self, prev_shot_id: str
    ) -> Optional[ShotExecutionPlan]:
        plan_path = f"04_production_slate/shots/{prev_shot_id}.json"
        try:
            data = self.workspace.read_json(plan_path)
            if isinstance(data.get("character_poses"), list):
                data["character_poses"] = {
                    p["entity_id"]: p["pose"] for p in data["character_poses"]
                }
            return ShotExecutionPlan(**data)
        except Exception as e:
            print(f"🎨 [Lead Animator] Could not load previous shot plan: {e}")
            return None

    def _build_distillation_prompt(
        self, plan: ShotExecutionPlan, action_text: str, master_style: str
    ) -> str:
        appearance_lines = []
        for entity_id, pose in plan.character_poses.items():
            try:
                lore = self.workspace.read_file(f"03_lore_bible/{entity_id}.md")
                appearance_lines.append(
                    f"- {entity_id}: {pose}. Appearance: {lore[:300]}"
                )
            except Exception:
                appearance_lines.append(f"- {entity_id}: {pose}")
        appearance_block = (
            "\n".join(appearance_lines) if appearance_lines else "See keyframe image."
        )

        dialogue_block = ""
        if hasattr(plan, "dialogue") and plan.dialogue:
            dialogue_desc = []
            for d in plan.dialogue:
                dialogue_desc.append(
                    f'- {d.get("speaker", "a character")} speaks with {d.get("emotion", "neutral")} emotion: "{d.get("line", "")}"'
                )
            dialogue_block = f"""
        DIALOGUE DURING THIS SHOT (characters should show lip movement and matching expressions):
        {chr(10).join(dialogue_desc)}"""

        return f"""Combine the following cinematic instructions into a single PURELY PHYSICAL motion description in English for a video generation model.
        
        STRICT RULES:
        1. Remove all character names, specific locations, brand names, and sensitive/abstract concepts.
        2. Replace character names with generic descriptors based on their appearance (e.g., "the young man in the dark blue coat", "the woman in the red silk dress").
        3. Focus ONLY on: light quality, camera movement, physical body dynamics, and character clothing/appearance for identification.
        4. Start the description by referencing the starting keyframe image. Use the exact token <<<image_1>>> to refer to it.
           Example: "Starting from <<<image_1>>>, the camera slowly dollies forward as the figure raises their hand..."
        5. Keep the description concise (under 200 words) but cinematically precise.
        6. When describing character motion, include what they are wearing so the video model maintains clothing consistency.
        7. NEVER include any on-screen text, subtitles, captions, dialogue bubbles, narration overlays, or watermarks in the description. The output is a PURE VISUAL motion sequence with zero text elements.
        8. If characters are speaking, describe their lip movement and facial expressions reflecting the emotion of the dialogue, but do NOT include the actual spoken words in the output.
        
        CHARACTER APPEARANCES AND POSES:
        {appearance_block}
        {dialogue_block}
        Style Guide: {master_style}
        Action: {action_text}
        Camera Plan: {plan.detailed_camera_plan}
        
        Output ONLY the distilled English description beginning with "Starting from <<<image_1>>>, ..."."""

    def _apply_style_and_generate(
        self,
        plan: ShotExecutionPlan,
        safe_prompt: str,
        image_path: str,
        proxy: Optional[str],
    ) -> str:
        shot_id = plan.shot_id

        if "<<<image_1>>>" not in safe_prompt:
            safe_prompt = f"Starting from <<<image_1>>>, {safe_prompt}"
            print(f"🎨 [Lead Animator] Injected <<<image_1>>> reference into prompt")

        style_key = self.project_config.get("video", {}).get("style", "cinematic")
        preset = self.project_config.get("style_presets", {}).get(style_key, {})
        prefix = preset.get("prompt_prefix", "")
        suffix = preset.get("prompt_suffix", "")

        full_prompt = f"{prefix} {safe_prompt} {suffix}"

        config = VideoGenerationConfig()
        config.enable_audio = True
        if plan.target_duration_ms:
            target_s = plan.target_duration_ms / 1000.0
            config.duration = 10 if target_s > 7 else 5
        if proxy:
            config.control_video_path = self.workspace.get_physical_path(proxy)

        video_path = f"05_dailies/{shot_id}/render.mp4"
        self.log_prompt(
            "LeadAnimator", shot_id, full_prompt, custom_path=f"{video_path}.prompt.txt"
        )

        print(f"🎨 [Lead Animator] Calling video generation API...")
        t0 = time.time()
        response = self.video_gen.generate_video(
            prompt=full_prompt,
            image_path=image_path,
            config=config,
        )
        elapsed = time.time() - t0

        self.workspace.save_media(video_path, response.video_bytes)
        print(
            f"🎨 [Lead Animator] Render complete: {video_path} ({len(response.video_bytes)} bytes, {elapsed:.1f}s)"
        )
        return video_path

    def generate_video_v2v(
        self, plan: ShotExecutionPlan, keyframe: str, proxy: Optional[str], prompt: str
    ) -> str:
        shot_id = plan.shot_id
        print(f"🎨 [Lead Animator] Executing render for {shot_id}")
        print(f"   Keyframe: {keyframe}")
        print(f"   Proxy: {proxy}")
        print(f"   Action prompt: {prompt[:200]}...")

        try:
            master_style = self.workspace.read_file("03_lore_bible/master_style.md")
        except Exception:
            master_style = "Cinematic, high fidelity."

        distillation_prompt = self._build_distillation_prompt(
            plan, prompt, master_style
        )

        print(f"🎨 [Lead Animator] Distilling motion prompt...")
        t0 = time.time()
        distilled_resp = self.llm.generate_text(
            distillation_prompt, system_prompt=LEAD_ANIMATOR_PROMPT
        )
        elapsed = time.time() - t0
        safe_prompt = distilled_resp.text.strip()
        print(
            f"🎨 [Lead Animator] Distilled prompt ({elapsed:.1f}s): {safe_prompt[:300]}"
        )

        keyframe_physical = self.workspace.get_physical_path(keyframe)
        return self._apply_style_and_generate(
            plan, safe_prompt, keyframe_physical, proxy
        )

    def generate_video_continuation(
        self,
        prev_plan: ShotExecutionPlan,
        current_plan: ShotExecutionPlan,
        last_frame_path: str,
        merged_action: str,
        proxy: Optional[str],
    ) -> str:
        shot_id = current_plan.shot_id
        print(f"🎨 [Lead Animator] Executing CONTINUATION render for {shot_id}")
        print(f"   Continuing from: {prev_plan.shot_id}")
        print(f"   Last frame: {last_frame_path}")
        print(f"   Merged action: {merged_action[:200]}...")

        try:
            master_style = self.workspace.read_file("03_lore_bible/master_style.md")
        except Exception:
            master_style = "Cinematic, high fidelity."

        distillation_prompt = self._build_distillation_prompt(
            current_plan, merged_action, master_style
        )

        print(f"🎨 [Lead Animator] Distilling continuation motion prompt...")
        t0 = time.time()
        distilled_resp = self.llm.generate_text(
            distillation_prompt, system_prompt=LEAD_ANIMATOR_PROMPT
        )
        elapsed = time.time() - t0
        safe_prompt = distilled_resp.text.strip()
        print(
            f"🎨 [Lead Animator] Distilled continuation prompt ({elapsed:.1f}s): {safe_prompt[:300]}"
        )

        return self._apply_style_and_generate(
            current_plan, safe_prompt, last_frame_path, proxy
        )


def lead_animator_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"🎨 [Lead Animator] === NODE ENTRY ===")
    plan = state.get("active_shot_plan")
    print(f"   active_shot_plan: {plan.shot_id if plan else None}")
    print(f"   current_keyframe_path: {state.get('current_keyframe_path')}")
    print(f"   current_proxy_path: {state.get('current_proxy_path')}")
    dailies = state.get("scene_dailies_paths", [])
    print(f"   scene_dailies_paths: {dailies}")
    print(
        f"   is_continuation: {getattr(plan, 'is_continuation', False) if plan else 'N/A'}"
    )
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = LeadAnimatorAgent.from_config(ws, state["project_config"])

    if not plan:
        print(f"🎨 [Lead Animator] === NODE EXIT === No plan (no-op)")
        return {}

    if getattr(plan, "is_continuation", False) and dailies:
        prev_video = dailies[-1]
        prev_shot_id = prev_video.split("/")[-2] if "/" in prev_video else None

        if prev_shot_id:
            prev_plan = agent._load_previous_shot_plan(prev_shot_id)

            if prev_plan:
                last_frame = agent._extract_last_frame(
                    prev_video, ws.get_physical_path(f"05_dailies/{plan.shot_id}")
                )
                if last_frame:
                    merged_action = f"{prev_plan.ending_composition_description} {plan.action_description}"
                    print(
                        f"🎨 [Lead Animator] CONTINUATION MODE — using last frame from {prev_shot_id}"
                    )
                    print(f"   Merged action: {merged_action[:300]}")
                    render_path = agent.generate_video_continuation(
                        prev_plan,
                        plan,
                        last_frame,
                        merged_action,
                        state.get("current_proxy_path"),
                    )
                    print(
                        f"🎨 [Lead Animator] === NODE EXIT === render={render_path} (continuation)"
                    )
                    return {"current_render_path": render_path}
                else:
                    print(
                        f"🎨 [Lead Animator] Last frame extraction failed, falling back to standard generation"
                    )
            else:
                print(
                    f"🎨 [Lead Animator] Could not load previous plan for {prev_shot_id}, falling back to standard generation"
                )
        else:
            print(
                f"🎨 [Lead Animator] Could not determine previous shot ID, falling back to standard generation"
            )
    elif getattr(plan, "is_continuation", False):
        print(
            f"🎨 [Lead Animator] is_continuation=True but no dailies available, falling back to standard generation"
        )
    else:
        print(f"🎨 [Lead Animator] Standard generation mode")

    render_path = agent.generate_video_v2v(
        plan,
        state["current_keyframe_path"],
        state.get("current_proxy_path"),
        plan.action_description,
    )

    print(f"🎨 [Lead Animator] === NODE EXIT === render={render_path}")
    return {"current_render_path": render_path}
