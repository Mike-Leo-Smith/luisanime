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
import shutil


RECONCILIATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reuse_last_frame": {
            "type": "BOOLEAN",
        },
        "reasoning": {
            "type": "STRING",
        },
        "updated_action_description": {
            "type": "STRING",
        },
        "updated_staging_description": {
            "type": "STRING",
        },
        "updated_character_poses": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "entity_id": {"type": "STRING"},
                    "pose": {"type": "STRING"},
                },
                "required": ["entity_id", "pose"],
            },
        },
    },
    "required": [
        "reuse_last_frame",
        "reasoning",
        "updated_action_description",
        "updated_staging_description",
        "updated_character_poses",
    ],
}


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

    def _reconcile_with_previous_frame(
        self,
        plan: ShotExecutionPlan,
        last_frame_path: str,
    ) -> tuple:
        """Analyze previous shot's last frame and reconcile the current shot plan.

        Returns:
            (reuse_last_frame, updated_plan): If reuse is True, the last frame
            should be used as the keyframe directly. Plan is always updated to
            reflect the actual state visible in the last frame.
        """
        print(
            f"📸 [Cinematographer] Reconciling plan with previous shot's last frame..."
        )
        print(f"   Shot: {plan.shot_id}")
        print(f"   Last frame: {last_frame_path}")

        prompt = f"""You are a cinematographer analyzing the LAST FRAME of the previous shot to prepare for the NEXT shot.

The attached image is the LAST FRAME (at 95% duration) of the previous shot's video.

CURRENT SHOT PLAN (from the Director):
- Shot ID: {plan.shot_id}
- Shot Scale: {plan.shot_scale}
- Camera Angle: {plan.camera_angle}
- Camera Movement: {plan.camera_movement}
- Action: {plan.action_description}
- Staging: {plan.staging_description}
- Character Poses: {json.dumps(plan.character_poses, ensure_ascii=False)}
- Active Entities: {plan.active_entities}

YOUR TASKS:

1. DESCRIBE what you see in the attached last frame: character positions, postures (standing/sitting/etc), objects held, facing directions, environment state.

2. DECIDE: Can this last frame be DIRECTLY REUSED as the starting keyframe for the current shot?
   Answer YES (reuse_last_frame=true) ONLY if ALL of these conditions are met:
   - The camera angle and shot scale in the last frame are reasonably compatible with the current shot plan
   - The character positions and states visible in the frame are compatible with the current shot's intended action
   - Using this frame would create smooth visual continuity
   Answer NO (reuse_last_frame=false) if:
   - The current shot requires a significantly different camera angle, scale, or framing
   - Characters need to be shown from a different perspective or at a different scale
   - The composition would be wrong for the planned action

3. UPDATE the shot plan to reflect REALITY from the last frame:
   - Adjust staging_description to match what characters are actually doing/where they actually are in the last frame
   - Adjust character_poses to match their actual posture/position/expression visible in the frame
   - Adjust action_description: keep the INTENDED action but fix the STARTING STATE to begin from where the previous shot actually ended

Respond in JSON:
```json
{{
  "reuse_last_frame": true or false,
  "reasoning": "brief explanation",
  "updated_action_description": "the action with corrected starting state",
  "updated_staging_description": "staging matching the last frame",
  "updated_character_poses": [
    {{"entity_id": "CharName", "pose": "standing, facing left, hands at sides"}}
  ]
}}
```"""

        physical_path = self.workspace.get_physical_path(last_frame_path)

        t0 = time.time()
        try:
            result = self.llm.generate_structured(
                prompt=prompt,
                response_schema=RECONCILIATION_SCHEMA,
                media_path=physical_path,
            )
        except Exception as e:
            print(f"📸 [Cinematographer] Reconciliation LLM call failed: {e}")
            return False, plan

        elapsed = time.time() - t0

        reuse = result.get("reuse_last_frame", False)
        reasoning = result.get("reasoning", "")
        print(f"📸 [Cinematographer] Reconciliation result ({elapsed:.1f}s):")
        print(f"   Reuse last frame: {reuse}")
        print(f"   Reasoning: {reasoning}")

        updated_plan = plan.model_copy()
        if result.get("updated_action_description"):
            updated_plan.action_description = result["updated_action_description"]
        if result.get("updated_staging_description"):
            updated_plan.staging_description = result["updated_staging_description"]
        if result.get("updated_character_poses"):
            poses = result["updated_character_poses"]
            if isinstance(poses, list):
                updated_plan.character_poses = {
                    p["entity_id"]: p["pose"] for p in poses if "entity_id" in p
                }
            elif isinstance(poses, dict):
                updated_plan.character_poses = poses

        if updated_plan.action_description != plan.action_description:
            print(f"   Updated action: {updated_plan.action_description[:200]}")
        if updated_plan.staging_description != plan.staging_description:
            print(f"   Updated staging: {updated_plan.staging_description[:200]}")
        if updated_plan.character_poses != plan.character_poses:
            print(f"   Updated poses: {updated_plan.character_poses}")

        return reuse, updated_plan

    def _persist_plan(self, plan: ShotExecutionPlan):
        """Overwrite the shot plan JSON on disk."""
        plan_path = f"04_production_slate/shots/{plan.shot_id}.json"
        data = plan.model_dump()
        # Convert character_poses dict back to list format for consistency with Director output
        if isinstance(data.get("character_poses"), dict):
            data["character_poses"] = [
                {"entity_id": k, "pose": v} for k, v in data["character_poses"].items()
            ]
        self.workspace.write_json(plan_path, data)
        print(f"📸 [Cinematographer] Persisted reconciled plan: {plan_path}")

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
                label = f"Image {img_idx}: LOCATION/ENVIRONMENT PANORAMA (21:9 wide) — reference for the setting's architecture, layout, and spatial arrangement. Use this panorama to understand the full environment context."
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

        entity_count = len(plan.active_entities)
        entity_list = (
            ", ".join(plan.active_entities) if plan.active_entities else "none"
        )

        full_prompt = f"""{prefix} 
STRICT RULE: This image MUST be the absolute STARTING FRAME (First Frame) of the shot.
STRICT RULE: Generate ONE single focused cinematic shot. NO multi-panels, NO montages.
STRICT RULE: Do NOT render any on-screen text, subtitles, captions, dialogue bubbles, manga speech balloons, narration text, watermarks, or any form of written words in the image. The output must be a PURE VISUAL frame with zero text elements.
STRICT RULE: This shot contains EXACTLY {entity_count} character(s): [{entity_list}]. Do NOT add any extra people, bystanders, crowd members, or background figures unless explicitly listed. Rendering more than {entity_count} human figure(s) is a critical error.

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

CHARACTER STATE CONTINUITY (CRITICAL — check previous shot end frame):
- Character posture and action state MUST follow logically from the previous shot. If a character stood up in the previous shot, they MUST be standing in this shot — NOT sitting or lying down. If a character picked up an object, they must still be holding it. If a character walked to the door, they must be near the door.
- Before composing, check the PREVIOUS SHOT END FRAME (95%) for each character's final posture (standing/sitting/lying/walking/holding), position, and facing direction. Your starting frame must be a plausible next moment in time.
- State transitions that contradict the previous shot (e.g., standing→sitting without a sit-down action described, holding an object→empty hands) are HARD ERRORS that will cause the keyframe to be rejected.

--- ATMOSPHERE, LIGHTING, AND COLOR TONE (AI短剧 CRITICAL) ---

LIGHTING AND ATMOSPHERE PROTOCOL — The AI video model renders ONLY what you describe. You MUST explicitly specify:
- LIGHTING: Describe the primary light source direction, quality (hard/soft), color temperature (warm/cool/neutral), and shadow characteristics. Example: "Warm golden-hour light streaming from the left window, casting long soft shadows across the desk. Key light on the subject's face from 45 degrees camera-left."
- COLOR TONE: The dominant color palette that sets the emotional register. Example: "Cold blue-gray corporate palette with desaturated walls and cool fluorescent highlights" or "Warm amber-and-brown intimate domestic tones."
- ATMOSPHERIC EFFECTS: Any visible environmental elements — dust motes in light beams, rain on windows, steam, breath in cold air, haze. Only include physically motivated effects.
These specifications are NOT optional — they have EQUAL PRIORITY with character positioning and spatial composition. A keyframe without explicit lighting/atmosphere direction will produce flat, lifeless video output.

STARTING COMPOSITION (Frame 0):
ACTION START: {plan.action_description}
INITIAL STAGING: {plan.staging_description}

CHARACTER APPEARANCE AND POSES:
{clothing_block}
{dialogue_block}
ERA CONTEXT: {plan.era_context}
ATMOSPHERE AND SETTING: {plan.setting_details}

LORE CONTEXT: {lore_context}

VISUAL STYLE REFERENCE:
{master_style}

TECHNICAL: Generate a 21:9 ultra-wide panoramic keyframe. This wide aspect ratio helps the AI video model understand the full spatial context of the scene. Photorealistic, masterpiece quality. {suffix}"""

        failed_keyframe_ref = []
        if feedback and retry_count > 0:
            failed_version_path = f"05_dailies/{shot_id}/keyframe_v{retry_count}.png"
            if self.workspace.exists(failed_version_path):
                failed_keyframe_ref = [failed_version_path]
                ref_manifest_lines.append(
                    f"Image {img_idx}: FAILED KEYFRAME (v{retry_count}) — this is the PREVIOUS ATTEMPT that was REJECTED by QA. See the revision feedback below for what went wrong. You MUST fix these issues in your new generation."
                )
                img_idx += 1

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
            f"📸 [Cinematographer] Final Prompt for {shot_id} v{version} ({len(full_prompt)} chars):\n{full_prompt[:500]}..."
        )

        all_refs = designs + continuity_refs + failed_keyframe_ref
        physical_refs = [self.workspace.get_physical_path(p) for p in all_refs]
        print(f"📸 [Cinematographer] Reference images: {len(physical_refs)} files")

        video_cfg = self.project_config.get("video", {})
        res_str = video_cfg.get("resolution", "1080p")
        width, height = 2016, 960
        if res_str == "720p":
            width, height = 1344, 640
        elif res_str == "4k":
            width, height = 4032, 1920
        print(
            f"📸 [Cinematographer] Resolution: {width}x{height} (21:9 panorama, {res_str})"
        )

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
                f"📸 [Cinematographer] ⚠️  Image generation failed for {shot_id} v{version}: {e}"
            )
            raise RuntimeError(
                f"Keyframe generation failed for {shot_id} v{version}: {e}"
            ) from e
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
            return {
                "current_keyframe_path": keyframe_path,
                "keyframe_is_reused_frame": True,
            }
        except Exception as e:
            print(
                f"📸 [Cinematographer] Last frame extraction failed ({e}), falling back to standard generation"
            )

    retry_count = state.get("keyframe_retry_count", 0)
    reconciled = False
    if not plan.is_continuation and dailies and retry_count == 0:
        prev_video = dailies[-1]
        physical_prev = ws.get_physical_path(prev_video)
        last_frame_dir = ws.get_physical_path(f"05_dailies/{plan.shot_id}")
        os.makedirs(last_frame_dir, exist_ok=True)
        last_frame_out = os.path.join(last_frame_dir, "reconcile_ref.png")
        try:
            probe = ffmpeg.probe(physical_prev)
            duration = float(probe["format"]["duration"])
            (
                ffmpeg.input(physical_prev, ss=duration * 0.95)
                .filter("scale", 1920, -1)
                .output(last_frame_out, vframes=1)
                .overwrite_output()
                .run(quiet=True)
            )
            reconcile_frame_path = f"05_dailies/{plan.shot_id}/reconcile_ref.png"
            reuse, updated_plan = agent._reconcile_with_previous_frame(
                plan, reconcile_frame_path
            )
            agent._persist_plan(updated_plan)
            plan = updated_plan
            reconciled = True

            if reuse:
                keyframe_out_path = os.path.join(last_frame_dir, "keyframe_v1.png")
                shutil.copy2(last_frame_out, keyframe_out_path)
                keyframe_path = f"05_dailies/{plan.shot_id}/keyframe_v1.png"
                print(
                    f"📸 [Cinematographer] Reconciliation: reusing last frame as keyframe: {keyframe_path}"
                )
                print(
                    f"📸 [Cinematographer] === NODE EXIT === keyframe={keyframe_path} (reconciled reuse)"
                )
                return {
                    "current_keyframe_path": keyframe_path,
                    "active_shot_plan": plan,
                    "keyframe_is_reused_frame": True,
                }
            else:
                print(
                    f"📸 [Cinematographer] Reconciliation: plan updated, proceeding to keyframe generation"
                )
        except Exception as e:
            print(
                f"📸 [Cinematographer] Reconciliation frame extraction failed ({e}), skipping reconciliation"
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
    if dailies:
        last_video = dailies[-1]
        continuity_refs = agent._extract_continuity_frames(last_video, plan.shot_id)

    keyframe_path = agent.generate_image_constrained(
        plan, lore, designs, continuity_refs, feedback=feedback, retry_count=retry_count
    )

    print(f"📸 [Cinematographer] === NODE EXIT === keyframe={keyframe_path}")
    result: Dict[str, Any] = {
        "current_keyframe_path": keyframe_path,
        "keyframe_is_reused_frame": False,
    }
    if reconciled:
        result["active_shot_plan"] = plan
    return result
