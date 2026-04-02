from typing import Dict, List, Optional
import os
import time
from pathlib import PurePosixPath
import ffmpeg
from src.agents.base import BaseExecutor
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.providers.base import VideoGenerationConfig
from src.agents.prompts import LEAD_ANIMATOR_PROMPT
from src.agents.shared import (
    extract_scene_id,
    load_master_style,
    load_style_preset,
    fetch_all_design_references,
    build_appearance_block,
    build_dialogue_block_video,
    build_spatial_block,
)


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
        self,
        plan: ShotExecutionPlan,
        action_text: str,
        master_style: str,
        ref_labels: Optional[List[tuple]] = None,
    ) -> str:
        appearance_block = build_appearance_block(self.workspace, plan.character_poses)
        dialogue_block = build_dialogue_block_video(plan.dialogue or [])

        ref_block = ""
        if ref_labels:
            ref_lines = []
            for token, label in ref_labels:
                ref_lines.append(f"- {token}: {label}")
            ref_block = f"""
        REFERENCE IMAGES (use these tokens to refer to character/environment reference images for visual consistency):
        {chr(10).join(ref_lines)}
        When describing a character's appearance or the environment, reference the corresponding image token so the video model maintains visual consistency."""

        spatial_block = build_spatial_block(
            plan.spatial_composition or {},
            shot_scale=plan.shot_scale or "medium",
            camera_angle=plan.camera_angle or "eye-level",
            for_video=True,
        )

        return f"""Combine the following cinematic instructions into a single PURELY PHYSICAL motion description in English for a video generation model.
        
        STRICT RULES:
        1. Remove all character names, specific locations, brand names, and sensitive/abstract concepts.
        2. Replace character names with DETAILED generic descriptors based on their FULL appearance — always include their clothing, hairstyle, and distinguishing features (e.g., "the young man in a dark navy double-breasted wool coat over a white collared shirt, with short black hair", "the slender woman in a crimson silk qipao with gold embroidery, hair pinned up with a jade hairpin").
        3. For EACH character visible in the shot, the output MUST include:
           a) Full clothing description (fabric, color, cut, layering, accessories)
           b) Body position and staging (where they stand/sit relative to the environment and other characters, facing direction)
           c) Specific physical action and gesture (what their hands, arms, head, torso are doing moment by moment)
           d) Facial expression and gaze direction
        4. Start the description by referencing the starting keyframe image. Use the exact token <<<image_1>>> to refer to it.
           Example: "Starting from <<<image_1>>>, the camera slowly dollies forward as the figure raises their hand..."
        5. The description should be DETAILED but CONCISE (250-350 words). Do NOT over-compress or omit character details, but avoid redundant adjectives and filler. Every character's clothing, position, and action must be explicitly described — the video model cannot infer what it is not told. The TOTAL prompt (including style prefix/suffix added later) must stay under 2500 characters.
        6. Include light quality, camera movement, and environmental atmosphere, but character appearance and action details take PRIORITY — never sacrifice character description for brevity.
        7. NEVER include any on-screen text, subtitles, captions, dialogue bubbles, narration overlays, or watermarks in the description. The output is a PURE VISUAL motion sequence with zero text elements.
        8. If characters are speaking, you MUST include their dialogue in your output. Write it as: the character says "exact spoken line here" (in the original language). The video model generates audio from your text, so spoken lines in quotation marks are essential for correct speech synthesis. Also describe lip movement, facial expressions, and body gestures matching the emotion of the dialogue.
        9. Include the reference image tokens (<<<image_2>>>, <<<image_3>>>, etc.) when first describing each character or the environment, so the video model can match their visual appearance and the spatial layout.
        
        SPATIAL CONSISTENCY:
        - Maintain the spatial layout visible in the starting keyframe <<<image_1>>>. Object positions, furniture, and architectural features must not shift during the video.
        - Character scale and body proportions must stay physically realistic relative to the environment throughout the motion.
        - Spatial relationships between characters (distance, facing direction, relative height) must evolve naturally from the starting keyframe — no teleporting or sudden repositioning.
        - If a character interacts with an object or another character, the contact point must be anatomically plausible and spatially consistent with the established layout.
        - Gaze direction and body orientation must match who/what the character is addressing at each moment.
        {ref_block}
        {spatial_block}
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
        reference_images: Optional[List[str]] = None,
    ) -> str:
        shot_id = plan.shot_id

        if "<<<image_1>>>" not in safe_prompt:
            safe_prompt = f"Starting from <<<image_1>>>, {safe_prompt}"
            print(f"🎨 [Lead Animator] Injected <<<image_1>>> reference into prompt")

        _style_key, prefix, suffix = load_style_preset(self.project_config)

        full_prompt = f"{prefix} {safe_prompt} {suffix}"

        # Kling API enforces 2500 char limit on prompt
        KLING_PROMPT_LIMIT = 2500
        if len(full_prompt) > KLING_PROMPT_LIMIT:
            overhead = len(prefix) + len(suffix) + 2  # 2 spaces
            max_safe_len = KLING_PROMPT_LIMIT - overhead
            if max_safe_len > 100:
                safe_prompt = safe_prompt[:max_safe_len]
                last_period = safe_prompt.rfind(".")
                if last_period > max_safe_len * 0.7:
                    safe_prompt = safe_prompt[: last_period + 1]
                full_prompt = f"{prefix} {safe_prompt} {suffix}"
                print(
                    f"🎨 [Lead Animator] Prompt truncated to {len(full_prompt)} chars (limit: {KLING_PROMPT_LIMIT})"
                )
            else:
                full_prompt = full_prompt[:KLING_PROMPT_LIMIT]
                print(
                    f"🎨 [Lead Animator] Prompt hard-truncated to {KLING_PROMPT_LIMIT} chars"
                )

        config = VideoGenerationConfig()
        config.enable_audio = True
        if reference_images:
            config.reference_images = reference_images
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

    def _build_ref_labels(
        self, plan: ShotExecutionPlan, ref_paths: List[str]
    ) -> List[tuple]:
        labels = []
        idx = 2
        for ref_path in ref_paths:
            basename = os.path.basename(ref_path).replace(".png", "")
            if basename in plan.active_entities:
                labels.append(
                    (f"<<<image_{idx}>>>", f"Character reference for {basename}")
                )
            elif "locations" in ref_path or "location" in ref_path.lower():
                labels.append(
                    (
                        f"<<<image_{idx}>>>",
                        f"Environment/location reference: {basename}",
                    )
                )
            else:
                labels.append((f"<<<image_{idx}>>>", f"Visual reference: {basename}"))
            idx += 1
        return labels

    def generate_video_v2v(
        self,
        plan: ShotExecutionPlan,
        keyframe: str,
        proxy: Optional[str],
        prompt: str,
        scene_path: Optional[str] = None,
    ) -> str:
        shot_id = plan.shot_id
        print(f"🎨 [Lead Animator] Executing render for {shot_id}")
        print(f"   Keyframe: {keyframe}")
        print(f"   Proxy: {proxy}")
        print(f"   Action prompt: {prompt[:200]}...")

        master_style = load_master_style(self.workspace)

        ref_paths = fetch_all_design_references(
            self.workspace,
            plan.active_entities,
            scene_path,
            scene_id=extract_scene_id(plan.shot_id),
            log_prefix="🎨 [Lead Animator]",
            return_physical=True,
        )
        ref_labels = self._build_ref_labels(plan, ref_paths)

        distillation_prompt = self._build_distillation_prompt(
            plan, prompt, master_style, ref_labels=ref_labels if ref_labels else None
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
            plan, safe_prompt, keyframe_physical, proxy, reference_images=ref_paths
        )

    def generate_video_continuation(
        self,
        prev_plan: ShotExecutionPlan,
        current_plan: ShotExecutionPlan,
        last_frame_path: str,
        merged_action: str,
        proxy: Optional[str],
        scene_path: Optional[str] = None,
    ) -> str:
        shot_id = current_plan.shot_id
        print(f"🎨 [Lead Animator] Executing CONTINUATION render for {shot_id}")
        print(f"   Continuing from: {prev_plan.shot_id}")
        print(f"   Last frame: {last_frame_path}")
        print(f"   Merged action: {merged_action[:200]}...")

        master_style = load_master_style(self.workspace)

        ref_paths = fetch_all_design_references(
            self.workspace,
            current_plan.active_entities,
            scene_path,
            scene_id=extract_scene_id(current_plan.shot_id),
            log_prefix="🎨 [Lead Animator]",
            return_physical=True,
        )
        ref_labels = self._build_ref_labels(current_plan, ref_paths)

        distillation_prompt = self._build_distillation_prompt(
            current_plan,
            merged_action,
            master_style,
            ref_labels=ref_labels if ref_labels else None,
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
            current_plan,
            safe_prompt,
            last_frame_path,
            proxy,
            reference_images=ref_paths,
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
    print(f"   is_continuation: {plan.is_continuation if plan else 'N/A'}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = LeadAnimatorAgent.from_config(ws, state["project_config"])

    if not plan:
        print(f"🎨 [Lead Animator] === NODE EXIT === No plan (no-op)")
        return {}

    scene_path = state.get("current_scene_path")

    if plan.is_continuation and dailies:
        prev_video = dailies[-1]
        # Extract prev_shot_id robustly using path parts
        prev_shot_id = (
            PurePosixPath(prev_video).parent.name if "/" in prev_video else None
        )

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
                        scene_path=scene_path,
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
    elif plan.is_continuation:
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
        scene_path=scene_path,
    )

    print(f"🎨 [Lead Animator] === NODE EXIT === render={render_path}")
    return {"current_render_path": render_path}
