from typing import Dict, Any, List, Optional
import json
import time
from src.agents.base import BaseExecutor
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.providers.base import ImageGenerationConfig
from src.agents.prompts import CINEMATOGRAPHER_PROMPT
from src.agents.shared import (
    extract_scene_id,
    load_master_style,
    load_style_preset,
    fetch_lore_context,
    fetch_design_references,
    fetch_location_references,
    build_clothing_block,
    build_dialogue_block_keyframe,
    build_spatial_block,
)

import ffmpeg
import os


class CinematographerAgent(BaseExecutor):
    def _extract_continuity_frames(self, video_path: str, shot_id: str) -> List[str]:
        """Extracts start, middle, and end frames from a video for continuity."""
        print(f"📸 [Cinematographer] Extracting continuity frames from {video_path}...")
        physical_video = self.workspace.get_physical_path(video_path)
        output_dir = self.workspace.get_physical_path(
            f"05_dailies/{shot_id}/continuity"
        )
        os.makedirs(output_dir, exist_ok=True)

        try:
            probe = ffmpeg.probe(physical_video)
            duration = float(probe["format"]["duration"])
        except (ffmpeg.Error, KeyError, ValueError, OSError) as e:
            print(f"📸 [Cinematographer] Could not probe video {video_path}: {e}")
            return []

        frames = []
        for i, pct in enumerate([0, 0.5, 0.95]):
            out_path = os.path.join(output_dir, f"ref_{i}.png")
            try:
                (
                    ffmpeg.input(physical_video, ss=duration * pct)
                    .filter("scale", 1280, -1)
                    .output(out_path, vframes=1)
                    .overwrite_output()
                    .run(quiet=True)
                )
                frames.append(f"05_dailies/{shot_id}/continuity/ref_{i}.png")
            except (ffmpeg.Error, OSError) as e:
                print(f"📸 [Cinematographer] Frame extraction at {pct:.0%} failed: {e}")
        return frames

    def generate_image_constrained(
        self,
        plan: ShotExecutionPlan,
        lore_context: str,
        designs: List[str],
        continuity_refs: List[str],
        feedback: Optional[str] = None,
        retry_count: int = 0,
    ) -> str:
        shot_id = plan.shot_id
        version = retry_count + 1
        print(
            f"📸 [Cinematographer] Generating STRICT STARTING FRAME for: {shot_id} (v{version})"
        )
        print(f"   Designs: {designs}")
        print(f"   Continuity refs: {continuity_refs}")
        print(f"   Feedback: {feedback[:200] if feedback else None}")

        master_style = load_master_style(self.workspace)
        _style_key, prefix, suffix = load_style_preset(self.project_config)

        ref_manifest_lines = []
        img_idx = 1
        for d in designs:
            if "/locations/" in d:
                label = f"Image {img_idx}: LOCATION/ENVIRONMENT DESIGN — reference for the setting's architecture, layout, and atmosphere."
            else:
                entity_name = d.rsplit("/", 1)[-1].replace(".png", "")
                label = f"Image {img_idx}: CHARACTER DESIGN for '{entity_name}' — reference for this character's appearance, clothing, and body type."
            ref_manifest_lines.append(label)
            img_idx += 1

        continuity_note = ""
        if continuity_refs:
            ref_manifest_lines.append(
                f"Image {img_idx}: PREVIOUS SHOT START FRAME (0%) — shows the environment and character state at the BEGINNING of the previous shot."
            )
            img_idx += 1
            if len(continuity_refs) > 1:
                ref_manifest_lines.append(
                    f"Image {img_idx}: PREVIOUS SHOT MIDDLE FRAME (50%) — shows the environment and character state at the MIDPOINT of the previous shot."
                )
                img_idx += 1
            if len(continuity_refs) > 2:
                ref_manifest_lines.append(
                    f"Image {img_idx}: PREVIOUS SHOT END FRAME (95%) — shows the environment and character state at the END of the previous shot."
                )
                img_idx += 1

            continuity_note = """PREVIOUS SHOT CONTINUITY REFERENCE (CRITICAL — read carefully):
The last 3 attached images are frames extracted from the PREVIOUS shot's video (start / middle / end).
They are provided ONLY as reference for:
  - Environment layout, lighting, and object placement continuity
  - Character positions, clothing state, and emotional progression
You MUST maintain logical continuity with the previous shot (e.g. same room layout, consistent character appearance, objects that were moved stay in their new positions).
You MUST NOT directly copy or reproduce the composition, camera angle, or framing of these reference frames. This is a NEW shot with its own camera setup — compose it according to the shot plan below."""

        ref_manifest = ""
        if ref_manifest_lines:
            ref_manifest = "ATTACHED REFERENCE IMAGES (in order):\n" + "\n".join(
                ref_manifest_lines
            )

        clothing_block = build_clothing_block(self.workspace, plan.character_poses)

        dialogue_block = build_dialogue_block_keyframe(plan.dialogue or [])

        spatial_block = build_spatial_block(
            plan.spatial_composition or {},
            shot_scale=plan.shot_scale or "medium",
            camera_angle=plan.camera_angle or "eye-level frontal",
            for_video=False,
        )

        full_prompt = f"""{prefix} 
STRICT RULE: This image MUST be the absolute STARTING FRAME (First Frame) of the shot.
STRICT RULE: Generate ONE single focused cinematic shot. NO multi-panels, NO montages.
STRICT RULE: Do NOT render any on-screen text, subtitles, captions, dialogue bubbles, manga speech balloons, narration text, watermarks, or any form of written words in the image. The output must be a PURE VISUAL frame with zero text elements.

{ref_manifest}

{continuity_note}
{spatial_block}

SPATIAL CONSISTENCY (CRITICAL — refer to the attached reference frames):
Maintain strict spatial coherence with previous shots in the same location. Specifically:
- Room layout, furniture placement, and object positions must stay consistent across different camera angles.
- Door swing direction (left-hinged vs right-hinged), window positions, and architectural features must not change.
- Relative positions of props (cups, books, lamps, etc.) on surfaces must remain where they were placed.
- If a character moved an object in a previous shot, it must remain in its new position.
- Lighting direction (e.g. window on the left casting light rightward) must be consistent with the established environment.
Use the provided reference images as ground truth for the spatial layout of this environment.

SPATIAL PROPORTIONS AND CHARACTER RELATIONSHIPS (CRITICAL):
- Object and character scale must be physically realistic relative to the environment (e.g., a door is ~2m tall, a chair reaches waist height, a person's head is roughly 1/7 of their body height).
- Character height and body proportions must remain consistent with their established design across all shots.
- Spatial relationships between characters must reflect their dramatic relationship: distance, height difference, facing direction, and body orientation all convey intent.
- Interaction state must be physically coherent: if one character is handing an object to another, both arms, the object, and the receiving hand must align in 3D space.
- Gaze direction, head tilt, and body lean must match who the character is addressing or what they are observing.
- If characters are in physical contact (touching, holding, pushing), the contact point must be anatomically plausible and consistent from both characters' perspectives.

CHARACTER POSITION CONTINUITY (CRITICAL for continuous scenes):
- In a continuous scene, characters do NOT teleport. If a character was on the left side of frame in the previous shot, they must still be on the left side (from the same spatial perspective) unless the shot plan explicitly describes them moving.
- Avoid drastic changes in character relative positions between consecutive shots. If two characters were facing each other across a table, they remain in those positions.
- When changing camera angle between shots, mentally rotate the spatial layout to ensure character left-right and near-far relationships are geometrically consistent from the new viewpoint.
- Refer to the PREVIOUS SHOT reference frames to verify character positions before composing this frame.

STARTING COMPOSITION (Frame 0):
ACTION START: {plan.action_description}
INITIAL STAGING: {plan.staging_description}

CHARACTER APPEARANCE AND POSES:
{clothing_block}
{dialogue_block}
ERA CONTEXT: {plan.era_context}
ATMOSPHERE: {plan.setting_details}

LORE CONTEXT: {lore_context}

VISUAL STYLE REFERENCE:
{master_style}

TECHNICAL: 8k resolution, photorealistic, masterpiece. {suffix}"""

        if feedback:
            full_prompt += f"\nREVISION FEEDBACK (FIX THESE): {feedback}"

        print(
            f"📸 [Cinematographer] Final Prompt for {shot_id} v{version} ({len(full_prompt)} chars):\n{full_prompt[:500]}..."
        )

        all_refs = designs + continuity_refs
        physical_refs = [self.workspace.get_physical_path(p) for p in all_refs]
        print(f"📸 [Cinematographer] Reference images: {len(physical_refs)} files")

        video_cfg = self.project_config.get("video", {})
        res_str = video_cfg.get("resolution", "1080p")
        width, height = 1920, 1080
        if res_str == "720p":
            width, height = 1280, 720
        elif res_str == "4k":
            width, height = 3840, 2160
        print(f"📸 [Cinematographer] Resolution: {width}x{height} ({res_str})")

        image_path = f"05_dailies/{shot_id}/keyframe_v{version}.png"
        self.log_prompt(
            "Cinematographer",
            shot_id,
            full_prompt,
            custom_path=f"{image_path}.prompt.txt",
        )

        config = ImageGenerationConfig(
            width=width, height=height, reference_media=physical_refs
        )
        t0 = time.time()
        response = self.image_gen.generate_image(prompt=full_prompt, config=config)
        elapsed = time.time() - t0

        self.workspace.save_media(image_path, response.image_bytes)
        print(
            f"📸 [Cinematographer] Starting Frame saved: {image_path} ({len(response.image_bytes)} bytes, {elapsed:.1f}s)"
        )
        return image_path


def cinematographer_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"📸 [Cinematographer] === NODE ENTRY ===")
    plan = state.get("active_shot_plan")
    print(f"   active_shot_plan: {plan.shot_id if plan else None}")
    print(f"   current_keyframe_path: {state.get('current_keyframe_path')}")
    print(
        f"   continuity_feedback: {str(state.get('continuity_feedback'))[:100] if state.get('continuity_feedback') else None}"
    )
    print(f"   scene_dailies_paths: {state.get('scene_dailies_paths', [])}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = CinematographerAgent.from_config(ws, state["project_config"])

    if not plan:
        print("📸 [Cinematographer] WARNING: No active shot plan found in state.")
        print(f"📸 [Cinematographer] === NODE EXIT === (no-op)")
        return {}

    dailies = state.get("scene_dailies_paths", [])

    if plan.is_continuation and dailies:
        print(
            f"📸 [Cinematographer] CONTINUATION SHOT — extracting last frame from previous video"
        )
        prev_video = dailies[-1]
        physical_video = ws.get_physical_path(prev_video)
        output_dir = ws.get_physical_path(f"05_dailies/{plan.shot_id}")
        os.makedirs(output_dir, exist_ok=True)
        keyframe_out = os.path.join(output_dir, "keyframe_v1.png")
        try:
            probe = ffmpeg.probe(physical_video)
            duration = float(probe["format"]["duration"])
            (
                ffmpeg.input(physical_video, ss=duration * 0.95)
                .filter("scale", 1920, -1)
                .output(keyframe_out, vframes=1)
                .overwrite_output()
                .run(quiet=True)
            )
            keyframe_path = f"05_dailies/{plan.shot_id}/keyframe_v1.png"
            print(
                f"📸 [Cinematographer] Continuation keyframe extracted: {keyframe_path}"
            )
            print(
                f"📸 [Cinematographer] === NODE EXIT === keyframe={keyframe_path} (continuation)"
            )
            return {"current_keyframe_path": keyframe_path}
        except Exception as e:
            print(
                f"📸 [Cinematographer] Last frame extraction failed ({e}), falling back to standard generation"
            )

    scene_id = extract_scene_id(plan.shot_id)
    lore = fetch_lore_context(
        ws, plan.active_entities, log_prefix="📸 [Cinematographer]"
    )
    designs = fetch_design_references(ws, plan.active_entities, scene_id=scene_id)
    scene_path = state.get("current_scene_path", "")
    if scene_path:
        designs += fetch_location_references(
            ws, scene_path, scene_id=scene_id, log_prefix="📸 [Cinematographer]"
        )
    feedback = state.get("continuity_feedback")

    # Identify last approved shot for continuity
    continuity_refs = []
    dailies = state.get("scene_dailies_paths", [])
    if dailies:
        last_video = dailies[-1]
        continuity_refs = agent._extract_continuity_frames(last_video, plan.shot_id)

    retry_count = state.get("render_retry_count", 0)
    keyframe_path = agent.generate_image_constrained(
        plan, lore, designs, continuity_refs, feedback=feedback, retry_count=retry_count
    )

    print(f"📸 [Cinematographer] === NODE EXIT === keyframe={keyframe_path}")
    return {"current_keyframe_path": keyframe_path}
