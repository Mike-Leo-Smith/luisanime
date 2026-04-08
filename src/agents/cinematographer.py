import math
import os
import time
from typing import Dict, List, Optional

import ffmpeg
import numpy as np
from PIL import Image, ImageDraw

from src.agents.base import BaseExecutor
from src.agents.shared import (
    build_clothing_block,
    build_dialogue_block_keyframe,
    extract_scene_id,
    fetch_all_design_references,
    fetch_lore_context,
    load_style_preset,
)
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.providers.base import ImageGenerationConfig


def _draw_arrow(draw: ImageDraw.Draw, x1, y1, x2, y2, color, width):
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    head_len = 15
    head_angle = 0.5
    for sign in (-1, 1):
        hx = int(x2 - head_len * math.cos(angle + sign * head_angle))
        hy = int(y2 - head_len * math.sin(angle + sign * head_angle))
        draw.line([(x2, y2), (hx, hy)], fill=color, width=width)


def _find_video_stream(probe: dict) -> dict:
    return next(s for s in probe["streams"] if s["codec_type"] == "video")


class CinematographerAgent(BaseExecutor):
    # ── prev-video → 2×2 grid storyboard ──────────────────────────

    def _extract_video_storyboard(
        self, video_path: str, output_path: str, num_frames: int = 4
    ) -> Optional[str]:
        physical_video = self.workspace.get_physical_path(video_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            probe = ffmpeg.probe(physical_video)
            vs = _find_video_stream(probe)
            width, height = int(vs["width"]), int(vs["height"])
            duration = float(probe["format"]["duration"])

            half_w, half_h = width // 2, height // 2
            timestamps = [duration * (i + 0.5) / num_frames for i in range(num_frames)]

            frames = []
            for i, ts in enumerate(timestamps):
                tmp = output_path.replace(".png", f"_tmp_{i}.png")
                (
                    ffmpeg.input(physical_video, ss=ts)
                    .filter("scale", half_w, half_h)
                    .output(tmp, vframes=1)
                    .overwrite_output()
                    .run(quiet=True)
                )
                frames.append(Image.open(tmp))

            # assemble 2×2 grid (same total resolution as original video)
            grid = Image.new("RGB", (half_w * 2, half_h * 2), (0, 0, 0))
            positions = [(0, 0), (half_w, 0), (0, half_h), (half_w, half_h)]
            for frame, pos in zip(frames, positions):
                grid.paste(frame, pos)

            # red arrows: 1→2 (right), 2→3 (diagonal Z), 3→4 (right)
            draw = ImageDraw.Draw(grid)
            color, w = (255, 0, 0), 4
            cx = [half_w // 2, half_w + half_w // 2, half_w // 2, half_w + half_w // 2]
            cy = [half_h // 2, half_h // 2, half_h + half_h // 2, half_h + half_h // 2]
            m = 20
            _draw_arrow(draw, cx[0] + m, cy[0], cx[1] - m, cy[1], color, w)
            _draw_arrow(
                draw,
                cx[1],
                cy[1] + m,
                cx[1] - half_w // 2,
                cy[1] + half_h - m,
                color,
                w,
            )
            _draw_arrow(draw, cx[2] + m, cy[2], cx[3] - m, cy[3], color, w)

            grid.save(output_path, "PNG")

            # clean up temp frames
            for i in range(num_frames):
                tmp = output_path.replace(".png", f"_tmp_{i}.png")
                if os.path.exists(tmp):
                    os.remove(tmp)

            print(
                f"📸 [Cinematographer] Previous shot storyboard extracted (2x2 grid): "
                f"{output_path} ({half_w * 2}x{half_h * 2})"
            )
            return output_path
        except Exception as e:
            print(f"📸 [Cinematographer] ⚠️  Failed to extract video storyboard: {e}")
            return None

    # ── keyframe (starting frame) generation ───────────────────────

    def generate_image_constrained(
        self,
        plan: ShotExecutionPlan,
        lore_context: str,
        designs: List[str],
        feedback: Optional[str] = None,
        retry_count: int = 0,
        storyboard_path: Optional[str] = None,
    ) -> str:
        shot_id = plan.shot_id
        version = retry_count + 1
        print(
            f"📸 [Cinematographer] Generating STRICT STARTING FRAME for: {shot_id} (v{version})"
        )
        print(f"   Designs: {designs}")
        print(f"   Feedback: {feedback[:200] if feedback else None}")

        _style_key, prefix, _suffix = load_style_preset(self.project_config)

        # build reference image manifest (storyboard first, then designs)
        ref_manifest_lines = []
        extra_physical_refs = []
        img_idx = 1

        if storyboard_path and self.workspace.exists(storyboard_path):
            ref_manifest_lines.append(
                f"Image {img_idx}: STORYBOARD for this shot — a 3-4 panel sequence "
                f"showing the planned action progression. Your keyframe MUST match "
                f"Panel 1 of this storyboard: same composition, character positions, "
                f"environment, and framing. Characters in the keyframe MUST closely "
                f"match how they appear in the storyboard — same face, hairstyle, "
                f"clothing, and overall look. This is the visual plan you are "
                f"realizing as a high-quality keyframe."
            )
            extra_physical_refs.append(
                self.workspace.get_physical_path(storyboard_path)
            )
            img_idx += 1

        for d in designs:
            if "/locations/" in d:
                label = (
                    f"Image {img_idx}: LOCATION/ENVIRONMENT DESIGN — reference "
                    f"for the setting's architecture, layout, and spatial arrangement."
                )
            else:
                entity_name = d.rsplit("/", 1)[-1].replace(".png", "")
                label = (
                    f"Image {img_idx}: CHARACTER DESIGN for '{entity_name}' — "
                    f"reference for this character's appearance, clothing, and body type."
                )
            ref_manifest_lines.append(label)
            img_idx += 1

        ref_manifest = ""
        if ref_manifest_lines:
            ref_manifest = "ATTACHED REFERENCE IMAGES (in order):\n" + "\n".join(
                ref_manifest_lines
            )

        clothing_block = build_clothing_block(self.workspace, plan.character_poses)
        dialogue_block = build_dialogue_block_keyframe(plan.dialogue or [])

        entity_count = len(plan.active_entities)
        entity_list = (
            ", ".join(plan.active_entities) if plan.active_entities else "none"
        )

        full_prompt = f"""{prefix}
RULES:
- This image is the STARTING FRAME (Frame 0) of the shot — a single frozen instant.
- ONE cinematic shot. No multi-panels, no montages.
- No on-screen text, subtitles, captions, dialogue bubbles, or watermarks.
- NO borders, padding, margins, letterboxing, or white edges. The image content MUST fill the entire canvas edge-to-edge.
- EXACTLY {entity_count} character(s): [{entity_list}]. No extra figures, no background people, no crowd members, no reflections of people not listed.
- CHARACTER IDENTITY (CRITICAL): Each character MUST closely match how they appear in the STORYBOARD (if attached) and the CHARACTER DESIGN reference images. Reproduce the SAME face (facial features, face shape, skin tone), SAME hairstyle (color, length, style), and SAME clothing (outfit, colors, accessories). Characters must be visually recognizable as the SAME person across storyboard, design sheets, and this keyframe.
- CHARACTER AESTHETICS: All characters must look NATURAL and appealing. Relaxed expressions (gentle smile, calm gaze, soft brow). Comfortable organic postures. No intense stares, exaggerated wide eyes, theatrical poses, stiff mannequin stances, or forced expressions. Characters should look like real people captured candidly.

{ref_manifest}

SCENE:
{plan.staging_description}

CHARACTER APPEARANCE AND POSES:
{clothing_block}
{dialogue_block}
ERA: {plan.era_context}
SETTING: {plan.setting_details}
FOCUS SUBJECT: {plan.focus_subject}

Generate a single keyframe image. No text, no subtitles, no captions, no watermarks."""

        # attach failed keyframe + revision feedback on retry
        failed_keyframe_ref = []
        if feedback and retry_count > 0:
            failed_version_path = f"05_dailies/{shot_id}/keyframe_v{retry_count}.png"
            if self.workspace.exists(failed_version_path):
                failed_keyframe_ref = [failed_version_path]

            full_prompt += f"""

REVISION FEEDBACK (CRITICAL — you MUST fix these issues):
The previous keyframe attempt (v{retry_count}) was REJECTED. {"The rejected image is attached as the LAST reference image." if failed_keyframe_ref else ""}
QA REJECTION REASON: {feedback}

You MUST:
1. Carefully study the rejection reason above.
2. {"Examine the attached failed keyframe to understand exactly what went wrong visually." if failed_keyframe_ref else ""}
3. Generate a NEW keyframe that fixes ALL listed issues while maintaining everything else correct.
4. Do NOT introduce new problems while fixing the old ones."""

        print(
            f"📸 [Cinematographer] Final Prompt for {shot_id} v{version} "
            f"({len(full_prompt)} chars):\n{full_prompt[:500]}..."
        )

        all_refs = designs + failed_keyframe_ref
        physical_refs = [
            self.workspace.get_physical_path(p) for p in all_refs
        ] + extra_physical_refs
        print(f"📸 [Cinematographer] Reference images: {len(physical_refs)} files")

        # resolution
        video_cfg = self.project_config.get("video", {})
        res_str = video_cfg.get("resolution", "1080p")
        res_map = {"720p": (1344, 640), "1080p": (2016, 960), "4k": (4032, 1920)}
        width, height = res_map.get(res_str, (2016, 960))
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
        try:
            response = self.image_gen.generate_image(prompt=full_prompt, config=config)
        except Exception as e:
            print(
                f"📸 [Cinematographer] ⚠️  Image generation failed for "
                f"{shot_id} v{version}: {e}"
            )
            raise RuntimeError(
                f"Keyframe generation failed for {shot_id} v{version}: {e}"
            ) from e
        elapsed = time.time() - t0

        self.workspace.save_media(image_path, response.image_bytes)
        print(
            f"📸 [Cinematographer] Starting Frame saved: {image_path} "
            f"({len(response.image_bytes)} bytes, {elapsed:.1f}s)"
        )
        return image_path

    # ── storyboard generation ──────────────────────────────────────

    def generate_storyboard(
        self,
        plan: ShotExecutionPlan,
        designs: List[str],
        prev_video_storyboard: Optional[str] = None,
    ) -> str:
        shot_id = plan.shot_id
        print(f"📸 [Cinematographer] Generating storyboard for: {shot_id}")

        # Determine target resolution (must match keyframe / Kling-compatible ratio)
        video_cfg = self.project_config.get("video", {})
        res_str = video_cfg.get("resolution", "1080p")
        res_map = {"720p": (1344, 640), "1080p": (2016, 960), "4k": (4032, 1920)}
        target_w, target_h = res_map.get(res_str, (2016, 960))
        print(
            f"📸 [Cinematographer] Storyboard target resolution: {target_w}x{target_h}"
        )

        _style_key, prefix, _suffix = load_style_preset(self.project_config)

        entity_count = len(plan.active_entities)
        entity_list = (
            ", ".join(plan.active_entities) if plan.active_entities else "none"
        )

        clothing_block = build_clothing_block(self.workspace, plan.character_poses)
        dialogue_block = build_dialogue_block_keyframe(plan.dialogue or [])

        # build reference manifest
        ref_manifest_lines = []
        all_ref_paths = []
        img_idx = 1

        if prev_video_storyboard and os.path.exists(prev_video_storyboard):
            all_ref_paths.append(prev_video_storyboard)
            ref_manifest_lines.append(
                f"Image {img_idx}: PREVIOUS SHOT'S FINAL STORYBOARD — 4 sampled "
                f"frames from the previous shot's video, arranged in 2×2 grid "
                f"chronologically with arrows. Use this to understand the visual "
                f"state, character positions, and environment at the END of the "
                f"previous shot. Your storyboard's first panel should naturally "
                f"continue from where this left off."
            )
            img_idx += 1

        for d in designs:
            all_ref_paths.append(d)
            if "/locations/" in d:
                label = f"Image {img_idx}: ENVIRONMENT DESIGN — spatial and architectural reference."
            else:
                entity_name = d.rsplit("/", 1)[-1].replace(".png", "")
                label = f"Image {img_idx}: CHARACTER DESIGN for '{entity_name}' — appearance and clothing reference."
            ref_manifest_lines.append(label)
            img_idx += 1

        ref_manifest = ""
        if ref_manifest_lines:
            ref_manifest = "ATTACHED REFERENCE IMAGES (in order):\n" + "\n".join(
                ref_manifest_lines
            )

        continuity_note = ""
        if prev_video_storyboard and os.path.exists(prev_video_storyboard):
            continuity_note = (
                "- CONTINUITY: The previous shot's final storyboard (Image 1) shows "
                "where the last shot ended. Panel 1 of YOUR storyboard should visually "
                "continue from that state — matching character positions, environment, "
                "and lighting.\n"
            )

        storyboard_prompt = f"""{prefix}
A storyboard panel sequence for a single cinematic shot. Draw 3-4 sequential panels LEFT to RIGHT showing key moments of this shot's action progression.

RULES:
- MATCH the visual style of the attached design reference images exactly. Use the SAME art style, color palette, rendering quality, and character designs.
- CHARACTER IDENTITY (CRITICAL): Each character MUST strictly replicate their attached CHARACTER DESIGN reference image. Reproduce the EXACT SAME face (facial features, face shape, skin tone), the EXACT SAME hairstyle (color, length, style), and the EXACT SAME clothing (outfit, colors, accessories). Characters must be visually recognizable as the SAME person shown in their design sheet. Do NOT alter, simplify, or reinterpret any character's appearance.
- EXACTLY {entity_count} character(s): [{entity_list}]. No extra figures, no background people, no crowd members, no reflections of people not listed.
- NO borders, padding, margins, or white edges around the image. Content must fill the entire canvas.
- CHARACTER AESTHETICS: All characters must have NATURAL, relaxed expressions and comfortable postures. No intense stares, exaggerated wide eyes, theatrical poses, or forced expressions. Subtle, understated body language only.
{continuity_note}- Use arrows to indicate camera movement direction: {plan.camera_movement}.
- No on-screen text, no dialogue bubbles, no watermarks.

{ref_manifest}

SHOT ACTION: {plan.action_description}
CAMERA: {plan.detailed_camera_plan}
STAGING: {plan.staging_description}
CHARACTERS: {clothing_block}
{dialogue_block}
SHOT SCALE: {plan.shot_scale} | CAMERA ANGLE: {plan.camera_angle}
FOCUS SUBJECT: {plan.focus_subject}

Generate a single storyboard image with 3-4 sequential panels in the SAME visual style as the reference images."""

        # resolve physical paths (prev_video_storyboard is absolute on disk)
        physical_refs = []
        for p in all_ref_paths:
            if os.path.exists(p):
                physical_refs.append(os.path.abspath(p))
            else:
                physical_refs.append(self.workspace.get_physical_path(p))

        config = ImageGenerationConfig(
            width=target_w, height=target_h, reference_media=physical_refs
        )

        storyboard_path = f"05_dailies/{shot_id}/storyboard.png"
        self.log_prompt(
            "Cinematographer",
            f"STORYBOARD_{shot_id}",
            storyboard_prompt,
            custom_path=f"{storyboard_path}.prompt.txt",
        )

        print(
            f"📸 [Cinematographer] Storyboard prompt ({len(storyboard_prompt)} chars): "
            f"{storyboard_prompt[:300]}..."
        )
        t0 = time.time()
        try:
            response = self.image_gen.generate_image(
                prompt=storyboard_prompt, config=config
            )
        except Exception as e:
            print(
                f"📸 [Cinematographer] ⚠️  Storyboard generation failed for {shot_id}: {e}"
            )
            return ""
        elapsed = time.time() - t0

        self.workspace.save_media(storyboard_path, response.image_bytes)

        physical_sb = self.workspace.get_physical_path(storyboard_path)
        try:
            sb_img = Image.open(physical_sb)
            if sb_img.size != (target_w, target_h):
                print(
                    f"📸 [Cinematographer] Fitting storyboard from "
                    f"{sb_img.size[0]}x{sb_img.size[1]} → {target_w}x{target_h}"
                )
                scale = min(target_w / sb_img.width, target_h / sb_img.height)
                new_w = int(sb_img.width * scale)
                new_h = int(sb_img.height * scale)
                scaled = sb_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
                canvas.paste(scaled, ((target_w - new_w) // 2, (target_h - new_h) // 2))
                canvas.save(physical_sb, "PNG")
        except Exception as e:
            print(f"📸 [Cinematographer] ⚠️  Storyboard fit failed: {e}")

        print(
            f"📸 [Cinematographer] Storyboard saved: {storyboard_path} "
            f"({target_w}x{target_h}, {elapsed:.1f}s)"
        )
        return storyboard_path


# ── node function (LangGraph entry point) ──────────────────────────


def _extract_prev_storyboard(agent, ws, plan, dailies):
    if not dailies:
        return None
    prev_video = dailies[-1]
    output_dir = ws.get_physical_path(f"05_dailies/{plan.shot_id}")
    os.makedirs(output_dir, exist_ok=True)
    sb_out = os.path.join(output_dir, "prev_shot_storyboard.png")
    result = agent._extract_video_storyboard(prev_video, sb_out)
    if result:
        result = os.path.abspath(result)
    print(f"📸 [Cinematographer] prev_video_storyboard for storyboard gen: {result}")
    return result


def cinematographer_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"📸 [Cinematographer] === NODE ENTRY ===")
    plan = state.get("active_shot_plan")
    print(f"   active_shot_plan: {plan.shot_id if plan else None}")
    print(f"   current_keyframe_path: {state.get('current_keyframe_path')}")
    print(
        f"   continuity_feedback: "
        f"{str(state.get('continuity_feedback'))[:100] if state.get('continuity_feedback') else None}"
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

    scene_id = extract_scene_id(plan.shot_id)
    scene_path = state.get("current_scene_path", "")
    designs = fetch_all_design_references(
        ws,
        plan.active_entities,
        scene_path or None,
        scene_id=scene_id,
        log_prefix="📸 [Cinematographer]",
    )

    # ── continuation shot: extract last frame as keyframe ──────────
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

            storyboard_path = ""
            if not ws.exists(f"05_dailies/{plan.shot_id}/storyboard.png"):
                prev_video_storyboard = _extract_prev_storyboard(
                    agent, ws, plan, dailies
                )
                storyboard_path = agent.generate_storyboard(
                    plan, designs, prev_video_storyboard=prev_video_storyboard
                )

            print(
                f"📸 [Cinematographer] === NODE EXIT === keyframe={keyframe_path} (continuation)"
            )
            return {
                "current_keyframe_path": keyframe_path,
                "current_storyboard_path": storyboard_path,
                "keyframe_is_reused_frame": True,
            }
        except Exception as e:
            print(
                f"📸 [Cinematographer] Last frame extraction failed ({e}), "
                f"falling back to standard generation"
            )

    # ── standard shot: storyboard → keyframe ───────────────────────
    retry_count = state.get("keyframe_retry_count", 0)

    lore = fetch_lore_context(
        ws, plan.active_entities, log_prefix="📸 [Cinematographer]"
    )
    feedback = state.get("continuity_feedback")

    # Ensure storyboard always exists before keyframe generation.
    # On retry, reuse the existing storyboard (don't regenerate).
    existing_storyboard = f"05_dailies/{plan.shot_id}/storyboard.png"
    if ws.exists(existing_storyboard):
        storyboard_path = existing_storyboard
        print(f"📸 [Cinematographer] Storyboard already exists: {storyboard_path}")
    else:
        prev_video_storyboard = _extract_prev_storyboard(agent, ws, plan, dailies)
        storyboard_path = agent.generate_storyboard(
            plan, designs, prev_video_storyboard=prev_video_storyboard
        )
        if not storyboard_path:
            print(
                "📸 [Cinematographer] ⚠️  Storyboard generation failed — "
                "proceeding without storyboard"
            )

    keyframe_path = agent.generate_image_constrained(
        plan,
        lore,
        designs,
        feedback=feedback,
        retry_count=retry_count,
        storyboard_path=storyboard_path or None,
    )

    print(f"📸 [Cinematographer] === NODE EXIT === keyframe={keyframe_path}")
    return {
        "current_keyframe_path": keyframe_path,
        "current_storyboard_path": storyboard_path,
        "keyframe_is_reused_frame": False,
    }
