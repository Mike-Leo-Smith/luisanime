from typing import Dict, List, Optional
import os
import time
from pathlib import PurePosixPath
import ffmpeg
from src.agents.base import BaseExecutor
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.providers.base import VideoGenerationConfig
from src.agents.shared import (
    load_style_preset,
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

    def _build_video_prompt(
        self,
        plan: ShotExecutionPlan,
        action_text: str,
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
            ref_lines = [f"- {token}: {label}" for token, label in ref_labels]
            ref_block = "REFERENCES:\n" + "\n".join(ref_lines)

        spatial_block = build_spatial_block(
            plan.spatial_composition or {},
            shot_scale=plan.shot_scale or "medium",
            camera_angle=plan.camera_angle or "eye-level",
            for_video=True,
        )

        entity_count = len(plan.active_entities)

        transition_line = ""
        if transition_mode:
            transition_line = "TRANSITION: Starting from previous shot's last frame. Transition naturally toward the target keyframe composition."

        if embeds:
            img1_token = video_gen.format_image_reference(1, "")
            starting_line = f"Starting from {img1_token}, "
        else:
            starting_line = "Starting from the provided keyframe, "

        duration_s = (
            plan.target_duration_ms / 1000.0 if plan.target_duration_ms else 5.0
        )

        parts = [
            f"{starting_line}{action_text}",
            f"Camera: {plan.detailed_camera_plan}",
            f"Focus Subject: {plan.focus_subject}" if plan.focus_subject else "",
            appearance_block,
            dialogue_block,
            spatial_block,
            ref_block,
            transition_line,
            f"Duration: {duration_s:.0f}s. EXACTLY {entity_count} character(s) visible.",
        ]

        return "\n".join(p for p in parts if p.strip())

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

        _style_key, prefix, _suffix = load_style_preset(self.project_config)

        no_text_rule = (
            "No text, no subtitles, no captions, no dialogue bubbles, no watermarks."
        )
        entity_count = len(plan.active_entities)
        no_extra_rule = f"EXACTLY {entity_count} character(s) visible. No additional people, crowd members, or background figures."
        full_prompt = f"{prefix} {safe_prompt} {no_text_rule} {no_extra_rule}"

        prompt_limit = video_gen.prompt_length_limit
        if prompt_limit > 0 and len(full_prompt) > prompt_limit:
            overhead = len(prefix) + len(no_text_rule) + len(no_extra_rule) + 3
            max_safe_len = prompt_limit - overhead
            if max_safe_len > 100:
                safe_prompt = safe_prompt[:max_safe_len]
                last_period = safe_prompt.rfind(".")
                if last_period > max_safe_len * 0.7:
                    safe_prompt = safe_prompt[: last_period + 1]
                full_prompt = f"{prefix} {safe_prompt} {no_text_rule} {no_extra_rule}"
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

    def _build_ref_labels(self, ref_paths: List[str]) -> List[tuple]:
        video_gen = self.video_gen
        assert video_gen is not None

        labels = []
        idx = 2
        for ref_path in ref_paths:
            basename = os.path.basename(ref_path).replace(".png", "")
            if basename == "storyboard":
                desc = "STORYBOARD — shot breakdown panels showing action progression, camera movement, and character staging for this shot. Use as motion/pacing guide."
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
        prev_last_frame: Optional[str] = None,
        storyboard_path: Optional[str] = None,
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

        ref_paths: List[str] = []
        if storyboard_path and self.workspace.exists(storyboard_path):
            ref_paths.append(self.workspace.get_physical_path(storyboard_path))
            print(f"🎨 [Lead Animator] Storyboard reference: {storyboard_path}")

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
            if ref_paths:
                storyboard_desc = "STORYBOARD — shot breakdown panels showing action progression, camera movement, and character staging. Use as motion/pacing guide."
                storyboard_token = video_gen.format_image_reference(3, storyboard_desc)
                ref_labels.append((storyboard_token, storyboard_desc))
        else:
            all_ref_paths = ref_paths
            ref_labels = self._build_ref_labels(ref_paths)

        safe_prompt = self._build_video_prompt(
            plan,
            prompt,
            ref_labels=ref_labels if ref_labels else None,
            transition_mode=transition_mode,
        )
        print(
            f"🎨 [Lead Animator] Video prompt ({len(safe_prompt)} chars): {safe_prompt[:300]}..."
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
        storyboard_path: Optional[str] = None,
    ) -> str:
        shot_id = current_plan.shot_id
        print(f"🎨 [Lead Animator] Executing CONTINUATION render for {shot_id}")
        print(f"   Continuing from: {prev_plan.shot_id}")
        print(f"   Last frame: {last_frame_path}")
        print(f"   Merged action: {merged_action[:200]}...")

        ref_paths: List[str] = []
        if storyboard_path and self.workspace.exists(storyboard_path):
            ref_paths.append(self.workspace.get_physical_path(storyboard_path))
            print(f"🎨 [Lead Animator] Storyboard reference: {storyboard_path}")

        ref_labels = self._build_ref_labels(ref_paths)

        safe_prompt = self._build_video_prompt(
            current_plan,
            merged_action,
            ref_labels=ref_labels if ref_labels else None,
        )
        print(
            f"🎨 [Lead Animator] Continuation video prompt ({len(safe_prompt)} chars): {safe_prompt[:300]}..."
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

    storyboard_path = state.get("current_storyboard_path")

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
                        storyboard_path=storyboard_path,
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
        storyboard_path=storyboard_path,
    )

    print(f"🎨 [Lead Animator] === NODE EXIT === render={render_path}")
    return {"current_render_path": render_path}
