from typing import Dict, Any, List, Optional
import json
import time
from src.agents.base import BaseQA
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.agents.prompts import CONTINUITY_SUPERVISOR_PROMPT


class ContinuitySupervisorAgent(BaseQA):
    def log_qa_report(self, shot_id: str, artifact_type: str, report: str):
        """Saves the QA report to the logs directory."""
        log_entry = (
            f"[{artifact_type} QA] SHOT: {shot_id}\nREPORT: {report}\n{'-' * 40}"
        )
        self.workspace.append_file("06_logs/qa_reports.log", log_entry)

    def select_best_keyframe(
        self, shot_id: str, qa_reports: List[Dict], plan: ShotExecutionPlan
    ) -> str:
        """When all keyframe attempts fail, select the version with the least severe issues."""
        print(
            f"🧐 [Continuity Supervisor] Best-of-N selection for {shot_id} ({len(qa_reports)} candidates)"
        )

        if len(qa_reports) == 1:
            return qa_reports[0]["path"]

        comparison_prompt = f"""You are reviewing {len(qa_reports)} keyframe attempts for a film shot. ALL of them failed QA, but we must pick the BEST one.

Shot description: {plan.action_description}
Staging: {plan.staging_description}

"""
        for i, entry in enumerate(qa_reports):
            comparison_prompt += f"--- Version {i + 1} ({entry['path']}) ---\nQA Report: {entry['feedback']}\n\n"

        comparison_prompt += f"""Pick the version with the LEAST SEVERE issues. Consider:
1. Minor composition issues are less severe than anatomical artifacts (extra fingers, distorted faces).
2. Slight staging differences are less severe than completely wrong framing.
3. Minor style drift is less severe than missing characters.

Respond with ONLY the version number (1, 2, or 3). Nothing else."""

        t0 = time.time()
        response = self.llm.generate_text(comparison_prompt)
        elapsed = time.time() - t0
        choice_text = response.text.strip()
        print(
            f"🧐 [Continuity Supervisor] LLM chose version: {choice_text} ({elapsed:.1f}s)"
        )

        try:
            idx = int("".join(c for c in choice_text if c.isdigit())) - 1
            idx = max(0, min(idx, len(qa_reports) - 1))
        except (ValueError, IndexError):
            idx = 0

        chosen = qa_reports[idx]["path"]
        print(f"🧐 [Continuity Supervisor] Best-of-N winner: {chosen}")
        return chosen

    def execute_keyframe_check(
        self, image_path: str, plan: ShotExecutionPlan, novel_context: str
    ) -> Dict:
        """
        Inspects the keyframe for AIGC artifacts, novel conformance, AND Starting Frame requirements.
        """
        print(f"🧐 [Continuity Supervisor] Keyframe check for {image_path}")
        print(f"   Shot: {plan.shot_id} | Action: {plan.action_description[:150]}...")

        entity_list = (
            ", ".join(plan.active_entities)
            if plan.active_entities
            else "none specified"
        )
        entity_count = len(plan.active_entities)

        prompt = f"""Analyze this generated keyframe for a film adaptation.
        
        STRICT REQUIREMENT: This MUST be the absolute FIRST FRAME (Frame 0) of the following shot.
        
        SHOT ACTION START: {plan.action_description}
        INITIAL STAGING: {plan.staging_description}
        INITIAL POSES: {json.dumps(plan.character_poses, ensure_ascii=False)}
        ACTIVE ENTITIES (GROUND TRUTH): [{entity_list}] — EXACTLY {entity_count} character(s) should appear.
        
        Original Novel Context: {novel_context}
        
        Evaluation Criteria:
        1. STARTING FRAME ACCURACY: Does the image accurately depict the STARTING STATE described? Focus on the overall scene setup, not pixel-perfect pose matching.
        2. NOVEL CONFORMANCE: Does the image reflect characters and mood from the novel?
        3. AIGC ARTIFACTS: Check for mutated hands, floating limbs, distorted faces.
        4. SPATIAL CONSISTENCY: If reference frames from previous shots are available, verify that the room layout, furniture positions, door orientations, window locations, prop placements, and lighting direction remain consistent across angles. Flag any contradictions in the physical environment.
        5. DUPLICATE / EXTRA ENTITIES (STRICT — MUST CHECK): First, count every distinct human figure visible in the image. The EXPECTED count is EXACTLY {entity_count} ({entity_list}). If you count MORE figures than {entity_count}, this is an automatic HARD FAIL — even if the extra figure is blurry, partially occluded, in the background, or appears to be a reflection (unless a mirror is explicitly part of the staging). Also check: if the SAME character appears to be rendered twice in different positions, or if a phantom/ghost figure is visible that does not correspond to any listed entity, this is a HARD FAIL. Duplicate, phantom, or extra characters are critical AIGC hallucination artifacts that MUST be caught.
        6. CHARACTER STATE CONTINUITY (STRICT — if previous shot reference frames are available): Check that each character's posture and action state is logically consistent with the PREVIOUS SHOT END FRAME. If a character was standing at the end of the previous shot, they must NOT be sitting or lying down in this frame (unless the shot plan explicitly describes them sitting down). If a character was holding an object, they should still have it. State regression (e.g., standing→sitting, holding→empty hands) without a described transition is a HARD FAIL.
        
        IMPORTANT TOLERANCE RULES:
        - Mirror reflections are NATURALLY laterally inverted (left-right flipped). Do NOT flag mirrored handedness, reversed text in mirrors, or laterally inverted details as inconsistencies — this is physically correct behavior.
        - Minor deviations in character pose, stance, body angle, or exact positioning relative to the textual description are ACCEPTABLE and should be considered reasonable artistic/cinematographic interpretation. Only flag pose issues if they fundamentally contradict the narrative (e.g., a character described as sitting is shown standing, or a character meant to face another is facing away).
        - Slight differences in character spacing, hand placement, or head tilt compared to the description are NOT grounds for rejection — the cinematographer has creative latitude in composing the frame.
        
        Respond with 'PASS' if the keyframe is acceptable (including minor artistic variations), or a detailed 'FAIL: [Reason]' ONLY for serious issues (AIGC artifacts, wrong characters, fundamentally wrong scene setup, broken spatial consistency)."""

        t0 = time.time()
        response = self.llm.analyze_image(
            image_path=self.workspace.get_physical_path(image_path), prompt=prompt
        )
        elapsed = time.time() - t0

        result_text = response.text
        self.log_qa_report(plan.shot_id, "KEYFRAME", result_text)

        print(
            f"🧐 [Continuity Supervisor] Keyframe QA result ({elapsed:.1f}s): {result_text[:300]}"
        )

        if "PASS" in result_text.upper() and "FAIL" not in result_text.upper():
            print("🧐 [Continuity Supervisor] Keyframe ✅ PASS")
            return {"status": "PASS"}

        print(f"🧐 [Continuity Supervisor] Keyframe ❌ REJECTED")
        return {"status": "FAIL", "feedback": result_text}

    def execute_cv_topology_check(self, video_path: str, shot_id: str) -> Dict:
        """Runs topology check (simulated with VLM)."""
        print(
            f"🧐 [Continuity Supervisor] Video Tier 1: Topology check for {video_path}"
        )
        prompt = "Analyze this video for anatomical consistency (hands, limbs, joint angles). Respond with PASS or FAIL_ANATOMY."

        t0 = time.time()
        response = self.llm.analyze_video(
            video_path=self.workspace.get_physical_path(video_path), prompt=prompt
        )
        elapsed = time.time() - t0

        self.log_qa_report(shot_id, "VIDEO_TOPOLOGY", response.text)

        print(
            f"🧐 [Continuity Supervisor] Tier 1 result ({elapsed:.1f}s): {response.text[:200]}"
        )
        if "PASS" in response.text.upper() and "FAIL" not in response.text.upper():
            print("🧐 [Continuity Supervisor] Video Tier 1 ✅ PASS")
            return {"status": "PASS"}
        print("🧐 [Continuity Supervisor] Video Tier 1 ❌ FAIL_ANATOMY")
        return {"status": "FAIL_ANATOMY", "feedback": response.text}

    def execute_vlm_semantic_check(
        self, video_path: str, shot_description: str, shot_id: str
    ) -> Dict:
        """Invokes a cloud VLM to verify semantic alignment."""
        print(
            f"🧐 [Continuity Supervisor] Video Tier 2: Semantic check for {video_path}"
        )
        prompt = f"Verify if this video matches the following description: '{shot_description}'. Respond with PASS or FAIL_SEMANTIC."

        t0 = time.time()
        response = self.llm.analyze_video(
            video_path=self.workspace.get_physical_path(video_path), prompt=prompt
        )
        elapsed = time.time() - t0

        self.log_qa_report(shot_id, "VIDEO_SEMANTIC", response.text)

        print(
            f"🧐 [Continuity Supervisor] Tier 2 result ({elapsed:.1f}s): {response.text[:200]}"
        )
        if "PASS" in response.text.upper() and "FAIL" not in response.text.upper():
            print("🧐 [Continuity Supervisor] Video Tier 2 ✅ PASS")
            return {"status": "PASS"}
        print("🧐 [Continuity Supervisor] Video Tier 2 ❌ FAIL_SEMANTIC")
        return {"status": "FAIL_SEMANTIC", "feedback": response.text}


def continuity_supervisor_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"🧐 [Continuity Supervisor] === NODE ENTRY ===")
    plan = state.get("active_shot_plan")
    print(f"   active_shot_plan: {plan.shot_id if plan else None}")
    print(f"   current_keyframe_path: {state.get('current_keyframe_path')}")
    print(f"   current_render_path: {state.get('current_render_path')}")
    print(f"   render_retry_count: {state.get('render_retry_count', 0)}")
    print(
        f"   continuity_feedback: {str(state.get('continuity_feedback'))[:100] if state.get('continuity_feedback') else None}"
    )
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = ContinuitySupervisorAgent.from_config(ws, state["project_config"])

    if not plan:
        print(f"🧐 [Continuity Supervisor] === NODE EXIT === No plan (no-op)")
        return {}

    # 1. Keyframe Validation
    if state.get("current_keyframe_path") and not state.get("current_render_path"):
        # Auto-PASS for continuation shots — the keyframe is extracted from an
        # already-approved previous video, so QA is unnecessary.
        if getattr(plan, "is_continuation", False):
            print(
                f"🧐 [Continuity Supervisor] Mode: KEYFRAME VALIDATION (CONTINUATION AUTO-PASS)"
            )
            print(
                f"🧐 [Continuity Supervisor] Keyframe is from previous video — skipping QA"
            )
            agent.log_qa_report(
                plan.shot_id,
                "KEYFRAME",
                "AUTO-PASS (continuation shot, keyframe from previous video)",
            )
            print(
                f"🧐 [Continuity Supervisor] === NODE EXIT === Continuation keyframe auto-approved → proceed to animation"
            )
            return {"continuity_feedback": None}

        print(f"🧐 [Continuity Supervisor] Mode: KEYFRAME VALIDATION")
        res = agent.execute_keyframe_check(
            state["current_keyframe_path"], plan, state.get("novel_text", "")[:5000]
        )
        if res["status"] == "PASS":
            print(
                f"🧐 [Continuity Supervisor] === NODE EXIT === Keyframe APPROVED → proceed to animation"
            )
            return {"continuity_feedback": None}
        else:
            retry = state.get("render_retry_count", 0) + 1

            if retry >= 3:
                print(
                    f"🧐 [Continuity Supervisor] 🚨 All {retry} keyframe attempts failed. Selecting best candidate..."
                )
                shot_id = plan.shot_id
                qa_reports = []
                for v in range(1, retry + 1):
                    path = f"05_dailies/{shot_id}/keyframe_v{v}.png"
                    if ws.exists(path):
                        qa_reports.append(
                            {"path": path, "feedback": res.get("feedback", "unknown")}
                        )

                try:
                    log_content = ws.read_file("06_logs/qa_reports.log")
                    sections = log_content.split("-" * 40)
                    version_feedbacks = {}
                    for section in sections:
                        if f"SHOT: {shot_id}" in section and "KEYFRAME QA" in section:
                            report_text = section.strip()
                            for v in range(1, retry + 1):
                                if (
                                    f"v{v}"
                                    in (state.get("current_keyframe_path") or "")
                                    or len(version_feedbacks) == v - 1
                                ):
                                    version_feedbacks[v] = report_text
                                    break
                except (FileNotFoundError, Exception) as e:
                    print(
                        f"🧐 [Continuity Supervisor] Could not parse QA log for best-of-N: {e}"
                    )
                    version_feedbacks = {}

                qa_entries = []
                for v in range(1, retry + 1):
                    path = f"05_dailies/{shot_id}/keyframe_v{v}.png"
                    if ws.exists(path):
                        fb = version_feedbacks.get(v, res.get("feedback", "unknown"))
                        qa_entries.append({"path": path, "feedback": fb})

                if qa_entries:
                    best_path = agent.select_best_keyframe(shot_id, qa_entries, plan)
                else:
                    best_path = state["current_keyframe_path"]

                print(
                    f"🧐 [Continuity Supervisor] === NODE EXIT === Best-of-N selected: {best_path} → proceed to animation"
                )
                return {
                    "continuity_feedback": None,
                    "current_keyframe_path": best_path,
                    "render_retry_count": 0,
                }

            print(
                f"🧐 [Continuity Supervisor] === NODE EXIT === Keyframe REJECTED (retry #{retry})"
            )
            return {
                "continuity_feedback": res["feedback"],
                "render_retry_count": retry,
            }

    # 2. Video Validation — auto-pass to save API costs
    if state.get("current_render_path"):
        print(
            f"🧐 [Continuity Supervisor] Mode: VIDEO VALIDATION (auto-pass, QA disabled)"
        )
        print(f"✅ [Continuity Supervisor] SHOT FULLY APPROVED: {plan.shot_id}")
        dailies = state.get("scene_dailies_paths", []) + [state["current_render_path"]]
        print(
            f"🧐 [Continuity Supervisor] === NODE EXIT === Shot approved, {len(dailies)} dailies total"
        )
        # IMPORTANT: Keep current_render_path set so the router knows we're
        # in render phase and can route to script_coordinator (not lead_animator).
        # script_coordinator will clear render/keyframe paths when setting up the next shot.
        return {
            "scene_dailies_paths": dailies,
            "continuity_feedback": None,
            "current_keyframe_path": None,
            "render_retry_count": 0,
        }

    print(f"🧐 [Continuity Supervisor] === NODE EXIT === Nothing to validate (no-op)")
    return {}
