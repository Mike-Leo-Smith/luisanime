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
        transition_mode: bool = False,
    ) -> str:
        appearance_block = build_appearance_block(self.workspace, plan.character_poses)
        dialogue_block = build_dialogue_block_video(plan.dialogue or [])

        video_gen = self.video_gen
        assert video_gen is not None
        embeds = video_gen.embeds_images_in_prompt

        ref_block = ""
        if ref_labels and embeds:
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

        entity_count = len(plan.active_entities)

        transition_block = ""
        if transition_mode and embeds:
            img1 = video_gen.format_image_reference(1, "")
            img2 = video_gen.format_image_reference(2, "")
            transition_block = f"""
        SHOT TRANSITION MODE:
        {img2} is the TARGET KEYFRAME for the CURRENT shot — use it as visual reference for the intended composition and framing.
        The video begins from the starting frame (provided separately). Transition naturally toward the target composition — the video model will decide the best cinematic transition (cut, pan, dissolve, etc.).
        When writing the prompt, start by describing the current state and then describe the scene evolution toward the target composition."""
        elif transition_mode:
            transition_block = """
        SHOT TRANSITION MODE:
        The starting frame is the LAST FRAME of the PREVIOUS shot — this is the video's starting point.
        A separate TARGET KEYFRAME is provided as reference for the intended composition and framing.
        The video begins from the starting frame. Transition naturally toward the target composition — the video model will decide the best cinematic transition (cut, pan, dissolve, etc.).
        Start by describing the current state and then describe the scene evolution toward the target composition."""

        if embeds:
            img1_token = video_gen.format_image_reference(1, "")
            starting_instruction = f"Starting from {img1_token}, ..."
            image_1_desc = "the starting keyframe image"
            if transition_mode:
                image_1_desc = "the LAST FRAME of the previous shot (starting point)"
            image_ref_rule = f"""4. Start the description by referencing {image_1_desc}. Use the exact token {img1_token} to refer to it.
           Example: "Starting from {img1_token}, the camera slowly dollies forward as the figure raises their hand..."
"""
            spatial_ref = f"Maintain the spatial layout visible in {img1_token}. Object positions, furniture, and architectural features must not shift during the video."
            ref_image_rule = "9. Include the reference image tokens when first describing each character or the environment, so the video model can match their visual appearance and the spatial layout."
        else:
            starting_instruction = "Starting from the provided keyframe, ..."
            image_ref_rule = """4. Start the description by referencing the starting keyframe image.
           Example: "Starting from the keyframe, the camera slowly dollies forward as the figure raises their hand..."
"""
            spatial_ref = "Maintain the spatial layout visible in the starting keyframe. Object positions, furniture, and architectural features must not shift during the video."
            ref_image_rule = "9. Describe each character's full appearance and the environment in rich detail so the video model can maintain visual consistency from the reference images provided separately."

        return f"""Combine the following cinematic instructions into a single PURELY PHYSICAL motion description in English for a video generation model. Apply ALL rules from your system prompt.
        
        DISTILLATION RULES:
        1. Replace character names with DETAILED generic descriptors including clothing, hairstyle, and distinguishing features (e.g., "the young man in a dark navy wool coat over a white collared shirt, short black hair").
        2. Remove specific locations, brand names, and abstract concepts.
        3. For EACH visible character, include: full clothing, body position/staging, specific physical actions, facial expression (physical descriptors only).
        {image_ref_rule}        5. Target 250-350 words. Never omit character details. Total prompt (with style prefix/suffix) must stay under 2500 characters.
        6. Include lighting (direction, color temperature, shadows), camera movement, color tone/palette. Character details still take PRIORITY.
        7. NO on-screen text, subtitles, captions, dialogue bubbles, watermarks.
        8. Include dialogue as: the character says "exact line" (original language). Describe matching lip movement and facial expressions.
        {ref_image_rule}        10. AUDIO: Describe ambient soundscape. ALLOWED: room tone, object sounds, dialogue, narration. FORBIDDEN: music, soundtrack, cinematic SFX.
        11. CHARACTER COUNT: EXACTLY {entity_count} character(s). No extras appear or vanish unless action explicitly describes entrance/exit.
        12. DIALOGUE TIMING: No dialogue in first 10% or last 10% of clip — place all dialogue in the middle 80%.
        {transition_block}
        SPATIAL CONSISTENCY:
        - {spatial_ref}
        - Character scale and proportions stay realistic throughout. Spatial relationships evolve naturally — no teleporting.
        - Interaction contact points must be anatomically plausible. Gaze/body orientation must match who/what is addressed.
        {ref_block}
        {spatial_block}
        CHARACTER APPEARANCES AND POSES:
        {appearance_block}
        {dialogue_block}
        Style Guide: {master_style}
        Action: {action_text}
        Camera Plan: {plan.detailed_camera_plan}
        
        Output ONLY the distilled English description beginning with "{starting_instruction}"."""

    def _apply_style_and_generate(
        self,
        plan: ShotExecutionPlan,
        safe_prompt: str,
        image_path: str,
        proxy: Optional[str],
        reference_images: Optional[List[str]] = None,
    ) -> str:
        shot_id = plan.shot_id

        video_gen = self.video_gen
        assert video_gen is not None

        if video_gen.embeds_images_in_prompt:
            img1_token = video_gen.format_image_reference(1, "")
            if img1_token and img1_token not in safe_prompt:
                safe_prompt = f"Starting from {img1_token}, {safe_prompt}"
                print(f"🎨 [Lead Animator] Injected {img1_token} reference into prompt")

        _style_key, prefix, suffix = load_style_preset(self.project_config)

        full_prompt = f"{prefix} {safe_prompt} {suffix}"

        prompt_limit = video_gen.prompt_length_limit
        if prompt_limit > 0 and len(full_prompt) > prompt_limit:
            overhead = len(prefix) + len(suffix) + 2  # 2 spaces
            max_safe_len = prompt_limit - overhead
            if max_safe_len > 100:
                safe_prompt = safe_prompt[:max_safe_len]
                last_period = safe_prompt.rfind(".")
                if last_period > max_safe_len * 0.7:
                    safe_prompt = safe_prompt[: last_period + 1]
                full_prompt = f"{prefix} {safe_prompt} {suffix}"
                print(
                    f"🎨 [Lead Animator] Prompt truncated to {len(full_prompt)} chars (limit: {prompt_limit})"
                )
            else:
                full_prompt = full_prompt[:prompt_limit]
                print(
                    f"🎨 [Lead Animator] Prompt hard-truncated to {prompt_limit} chars"
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
        response = video_gen.generate_video(
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
        video_gen = self.video_gen
        assert video_gen is not None

        labels = []
        idx = 2
        for ref_path in ref_paths:
            basename = os.path.basename(ref_path).replace(".png", "")
            if basename in plan.active_entities:
                desc = f"Character reference for {basename}"
                token = video_gen.format_image_reference(idx, desc)
                labels.append((token, desc))
            elif "locations" in ref_path or "location" in ref_path.lower():
                desc = f"Environment/location PANORAMA (21:9 wide): {basename} — use for spatial context"
                token = video_gen.format_image_reference(idx, desc)
                labels.append((token, desc))
            else:
                desc = f"Visual reference: {basename}"
                token = video_gen.format_image_reference(idx, desc)
                labels.append((token, desc))
            idx += 1
        return labels

    def generate_video_v2v(
        self,
        plan: ShotExecutionPlan,
        keyframe: str,
        proxy: Optional[str],
        prompt: str,
        scene_path: Optional[str] = None,
        prev_last_frame: Optional[str] = None,
    ) -> str:
        shot_id = plan.shot_id
        transition_mode = prev_last_frame is not None
        print(f"🎨 [Lead Animator] Executing render for {shot_id}")
        print(f"   Keyframe: {keyframe}")
        print(f"   Proxy: {proxy}")
        print(f"   Transition mode: {transition_mode}")
        if transition_mode:
            print(f"   Prev last frame (first_frame): {prev_last_frame}")
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

        if transition_mode:
            video_gen = self.video_gen
            assert video_gen is not None

            keyframe_physical = self.workspace.get_physical_path(keyframe)
            all_ref_paths = [keyframe_physical] + ref_paths
            target_desc = (
                "TARGET KEYFRAME for this shot — transition toward this composition"
            )
            target_token = video_gen.format_image_reference(2, target_desc)
            ref_labels = [(target_token, target_desc)]
            idx = 3
            for ref_path in ref_paths:
                basename = os.path.basename(ref_path).replace(".png", "")
                if basename in plan.active_entities:
                    desc = f"Character reference for {basename}"
                    token = video_gen.format_image_reference(idx, desc)
                    ref_labels.append((token, desc))
                elif "locations" in ref_path or "location" in ref_path.lower():
                    desc = f"Environment/location PANORAMA (21:9 wide): {basename} — use for spatial context"
                    token = video_gen.format_image_reference(idx, desc)
                    ref_labels.append((token, desc))
                else:
                    desc = f"Visual reference: {basename}"
                    token = video_gen.format_image_reference(idx, desc)
                    ref_labels.append((token, desc))
                idx += 1
        else:
            all_ref_paths = ref_paths
            ref_labels = self._build_ref_labels(plan, ref_paths)

        distillation_prompt = self._build_distillation_prompt(
            plan,
            prompt,
            master_style,
            ref_labels=ref_labels if ref_labels else None,
            transition_mode=transition_mode,
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

        if transition_mode:
            first_frame_physical = self.workspace.get_physical_path(prev_last_frame)
        else:
            first_frame_physical = self.workspace.get_physical_path(keyframe)

        return self._apply_style_and_generate(
            plan,
            safe_prompt,
            first_frame_physical,
            proxy,
            reference_images=all_ref_paths,
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

    prev_last_frame_path: Optional[str] = None
    keyframe_is_reused = state.get("keyframe_is_reused_frame", False)
    if dailies and not keyframe_is_reused and not plan.is_continuation:
        prev_video = dailies[-1]
        prev_last_frame_path_phys = agent._extract_last_frame(
            prev_video, ws.get_physical_path(f"05_dailies/{plan.shot_id}")
        )
        if prev_last_frame_path_phys:
            prev_last_frame_path = f"05_dailies/{plan.shot_id}/last_frame.png"
            print(
                f"🎨 [Lead Animator] TRANSITION MODE — prev last frame as first_frame, keyframe as reference target"
            )
        else:
            print(
                f"🎨 [Lead Animator] Could not extract prev last frame, using keyframe as first_frame"
            )

    render_path = agent.generate_video_v2v(
        plan,
        state["current_keyframe_path"],
        state.get("current_proxy_path"),
        plan.action_description,
        scene_path=scene_path,
        prev_last_frame=prev_last_frame_path,
    )

    print(f"🎨 [Lead Animator] === NODE EXIT === render={render_path}")
    return {"current_render_path": render_path}
