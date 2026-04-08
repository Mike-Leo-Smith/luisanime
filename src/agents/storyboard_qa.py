from typing import Dict, List, Optional
import json
import time
from src.agents.base import BaseQA
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.agents.shared import extract_scene_id, fetch_all_design_references


class StoryboardQAAgent(BaseQA):
    def evaluate_storyboard(
        self,
        storyboard_path: str,
        plan: ShotExecutionPlan,
        design_refs: List[str],
    ) -> Dict:
        print(f"🔍 [Storyboard QA] Evaluating storyboard: {storyboard_path}")
        print(f"   Shot: {plan.shot_id} | Entities: {plan.active_entities}")
        print(f"   Design refs: {len(design_refs)} images")

        entity_count = len(plan.active_entities)
        entity_list = (
            ", ".join(plan.active_entities) if plan.active_entities else "none"
        )

        ref_manifest_lines = []
        ref_manifest_lines.append(
            "Image 1: STORYBOARD being evaluated (the image under review)."
        )
        for i, d in enumerate(design_refs, 2):
            if "/locations/" in d:
                ref_manifest_lines.append(
                    f"Image {i}: ENVIRONMENT DESIGN — the reference for this location."
                )
            else:
                entity_name = d.rsplit("/", 1)[-1].replace(".png", "")
                ref_manifest_lines.append(
                    f"Image {i}: CHARACTER DESIGN for '{entity_name}' — "
                    f"the canonical face, hairstyle, and clothing reference."
                )

        ref_manifest = "ATTACHED IMAGES (in order):\n" + "\n".join(ref_manifest_lines)

        prompt = f"""Analyze this storyboard for production quality before it is used for keyframe generation.

{ref_manifest}

SHOT DETAILS:
Action: {plan.action_description}
Staging: {plan.staging_description}
Camera: {plan.camera_movement} | {plan.detailed_camera_plan}
Shot Scale: {plan.shot_scale} | Camera Angle: {plan.camera_angle}
Active Entities (GROUND TRUTH): [{entity_list}] — EXACTLY {entity_count} character(s).
Focus Subject: {plan.focus_subject}
Character Poses: {json.dumps(plan.character_poses, ensure_ascii=False)}

Evaluation Criteria:
1. PANEL COUNT: The storyboard MUST contain 3-4 sequential panels arranged LEFT to RIGHT. If there are fewer than 3 or more than 5 panels, this is a FAIL.
2. CHARACTER IDENTITY (CRITICAL): Compare each character in the storyboard against their attached CHARACTER DESIGN reference images. Each character MUST be visually recognizable as the SAME person: same face (facial features, face shape, skin tone), same hairstyle (color, length, style), same clothing (outfit, colors, accessories). If any character's face, hair, or clothing visibly differs from their design sheet, flag it as: "CHARACTER IDENTITY MISMATCH: [character name] — [describe the difference]".
3. ENTITY COUNT: EXACTLY {entity_count} character(s) should appear: [{entity_list}]. No extra figures, no background people, no phantom duplicates.
4. PANEL 1 STAGING: Panel 1 (the leftmost panel) should match the INITIAL STAGING described above — correct character positions, environment, and framing.
5. NO TEXT/FORBIDDEN ELEMENTS: No dialogue bubbles, captions, text labels, watermarks. No borders or heavy padding between panels.
6. CHARACTER AESTHETICS: Characters should have NATURAL expressions and postures. No intense stares, exaggerated wide eyes, theatrical poses, or forced expressions.
7. ACTION CONTINUITY: Panels should show a logical progression of the shot's action, not random disconnected scenes.

TOLERANCE:
- Minor stylistic variations between design sheet and storyboard rendering are acceptable (different rendering quality/detail level is expected).
- Small differences in exact pose or body angle from the shot description are acceptable.
- The key requirement is CHARACTER IDENTITY — the characters must be recognizably the SAME people as in their design sheets.

Respond with 'PASS' if the storyboard meets production standards, or 'FAIL: [Reason]' with specific issues. Only fail for significant problems."""

        image_paths = [self.workspace.get_physical_path(storyboard_path)]
        for d in design_refs:
            physical = self.workspace.get_physical_path(d)
            image_paths.append(physical)

        t0 = time.time()
        if len(image_paths) > 1:
            response = self.llm.analyze_images(image_paths=image_paths, prompt=prompt)
        else:
            response = self.llm.analyze_image(image_path=image_paths[0], prompt=prompt)
        elapsed = time.time() - t0

        result_text = response.text
        print(f"🔍 [Storyboard QA] Result ({elapsed:.1f}s): {result_text[:300]}")

        log_entry = f"[STORYBOARD QA] SHOT: {plan.shot_id}\nPATH: {storyboard_path}\nRESULT: {result_text}\n{'-' * 40}"
        self.workspace.append_file("06_logs/qa_reports.log", log_entry)

        if "PASS" in result_text.upper() and "FAIL" not in result_text.upper():
            print(f"🔍 [Storyboard QA] Storyboard ✅ PASS")
            return {"status": "PASS"}

        print(f"🔍 [Storyboard QA] Storyboard ❌ FAIL")
        return {"status": "FAIL", "feedback": result_text}


def storyboard_qa_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"🔍 [Storyboard QA] === NODE ENTRY ===")
    plan = state.get("active_shot_plan")
    storyboard_path = state.get("current_storyboard_path")
    storyboard_retry = state.get("storyboard_retry_count", 0)
    storyboard_feedback = state.get("storyboard_feedback")
    print(f"   active_shot_plan: {plan.shot_id if plan else None}")
    print(f"   current_storyboard_path: {storyboard_path}")
    print(f"   storyboard_retry_count: {storyboard_retry}")
    print(
        f"   storyboard_feedback: {storyboard_feedback[:100] if storyboard_feedback else None}"
    )
    print(f"{'=' * 60}")

    if not plan:
        print(f"🔍 [Storyboard QA] === NODE EXIT === No plan (no-op)")
        return {}

    if not storyboard_path:
        print(f"🔍 [Storyboard QA] === NODE EXIT === No storyboard to check")
        return {"storyboard_feedback": None, "storyboard_retry_count": 0}

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])

    if not ws.exists(storyboard_path):
        print(f"🔍 [Storyboard QA] ⚠️  Storyboard file not found: {storyboard_path}")
        print(f"🔍 [Storyboard QA] === NODE EXIT === File missing, skip QA")
        return {"storyboard_feedback": None, "storyboard_retry_count": 0}

    agent = StoryboardQAAgent.from_config(ws, state["project_config"])

    scene_id = extract_scene_id(plan.shot_id)
    scene_path = state.get("current_scene_path", "")

    design_refs = fetch_all_design_references(
        ws,
        plan.active_entities,
        scene_path or None,
        scene_id=scene_id,
        log_prefix="🔍 [Storyboard QA]",
    )

    result = agent.evaluate_storyboard(storyboard_path, plan, design_refs)

    if result["status"] == "PASS":
        print(
            f"🔍 [Storyboard QA] === NODE EXIT === Storyboard APPROVED → proceed to keyframe"
        )
        return {"storyboard_feedback": None, "storyboard_retry_count": 0}

    retry = storyboard_retry + 1

    if retry >= 3:
        print(
            f"🔍 [Storyboard QA] 🚨 Max retries reached ({retry}). Accepting storyboard as-is."
        )
        print(f"🔍 [Storyboard QA] === NODE EXIT === Max retries, force-accepting")
        return {"storyboard_feedback": None, "storyboard_retry_count": 0}

    print(f"🔍 [Storyboard QA] === NODE EXIT === Storyboard REJECTED (retry #{retry})")
    return {
        "storyboard_feedback": result.get("feedback", "Quality issues detected"),
        "storyboard_retry_count": retry,
    }
