from typing import Dict, Any, List, Optional
import json
from src.agents.base import BaseQA
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.agents.prompts import CONTINUITY_SUPERVISOR_PROMPT

class ContinuitySupervisorAgent(BaseQA):
    def log_qa_report(self, shot_id: str, artifact_type: str, report: str):
        """Saves the QA report to the logs directory."""
        log_entry = f"[{artifact_type} QA] SHOT: {shot_id}\nREPORT: {report}\n{'-'*40}"
        self.workspace.append_file("06_logs/qa_reports.log", log_entry)

    def execute_keyframe_check(self, image_path: str, plan: ShotExecutionPlan, novel_context: str) -> Dict:
        """
        Inspects the keyframe for AIGC artifacts, novel conformance, AND Starting Frame requirements.
        """
        print(f"🧐 [Continuity Supervisor] Keyframe check for {image_path}...")
        
        prompt = f"""Analyze this generated keyframe for a film adaptation.
        
        STRICT REQUIREMENT: This MUST be the absolute FIRST FRAME (Frame 0) of the following shot.
        
        SHOT ACTION START: {plan.action_description}
        INITIAL STAGING: {plan.staging_description}
        INITIAL POSES: {json.dumps(plan.character_poses, ensure_ascii=False)}
        
        Original Novel Context: {novel_context}
        
        Evaluation Criteria:
        1. STARTING FRAME ACCURACY: Does the image accurately depict the EXACT starting state described?
        2. NOVEL CONFORMANCE: Does the image reflect characters and mood from the novel?
        3. AIGC ARTIFACTS: Check for mutated hands, floating limbs, distorted faces.
        
        Respond with 'PASS' if perfect, or a detailed 'FAIL: [Reason]' if it needs regeneration."""
        
        response = self.llm.analyze_image(
            image_path=self.workspace.get_physical_path(image_path),
            prompt=prompt
        )
        
        result_text = response.text
        self.log_qa_report(plan.shot_id, "KEYFRAME", result_text)
        
        if "PASS" in result_text.upper() and "FAIL" not in result_text.upper():
            print("🧐 [Continuity Supervisor] Keyframe PASS.")
            return {"status": "PASS"}
        
        print(f"🧐 [Continuity Supervisor] Keyframe REJECTED: {result_text}")
        return {"status": "FAIL", "feedback": result_text}

    def execute_cv_topology_check(self, video_path: str, shot_id: str) -> Dict:
        """Runs topology check (simulated with VLM)."""
        print(f"🧐 [Continuity Supervisor] Video Tier 1: Topology check for {video_path}...")
        prompt = "Analyze this video for anatomical consistency (hands, limbs, joint angles). Respond with PASS or FAIL_ANATOMY."
        
        response = self.llm.analyze_video(
            video_path=self.workspace.get_physical_path(video_path),
            prompt=prompt
        )
        
        self.log_qa_report(shot_id, "VIDEO_TOPOLOGY", response.text)
        
        if "PASS" in response.text.upper() and "FAIL" not in response.text.upper():
            print("🧐 [Continuity Supervisor] Video Tier 1 PASS.")
            return {"status": "PASS"}
        return {"status": "FAIL_ANATOMY", "feedback": response.text}
        
    def execute_vlm_semantic_check(self, video_path: str, shot_description: str, shot_id: str) -> Dict:
        """Invokes a cloud VLM to verify semantic alignment."""
        print(f"🧐 [Continuity Supervisor] Video Tier 2: Semantic check for {video_path}...")
        prompt = f"Verify if this video matches the following description: '{shot_description}'. Respond with PASS or FAIL_SEMANTIC."
        
        response = self.llm.analyze_video(
            video_path=self.workspace.get_physical_path(video_path),
            prompt=prompt
        )
        
        self.log_qa_report(shot_id, "VIDEO_SEMANTIC", response.text)
        
        if "PASS" in response.text.upper() and "FAIL" not in response.text.upper():
            print("🧐 [Continuity Supervisor] Video Tier 2 PASS.")
            return {"status": "PASS"}
        return {"status": "FAIL_SEMANTIC", "feedback": response.text}

def continuity_supervisor_node(state: AFCState) -> Dict:
    from src.pipeline.workspace import AgenticWorkspace
    ws = AgenticWorkspace(state["workspace_root"])
    agent = ContinuitySupervisorAgent.from_config(ws, state["project_config"])
    
    plan = state.get("active_shot_plan")
    if not plan:
        return {}
    
    # 1. Keyframe Validation
    if state.get("current_keyframe_path") and not state.get("current_render_path"):
        res = agent.execute_keyframe_check(
            state["current_keyframe_path"], 
            plan,
            state.get("novel_text", "")[:5000]
        )
        if res["status"] == "PASS":
            return {"continuity_feedback": None}
        else:
            return {
                "continuity_feedback": res["feedback"],
                "render_retry_count": state.get("render_retry_count", 0) + 1
            }

    # 2. Video Validation
    if state.get("current_render_path"):
        res = agent.execute_cv_topology_check(state["current_render_path"], plan.shot_id)
        if res["status"] == "PASS":
            res = agent.execute_vlm_semantic_check(state["current_render_path"], plan.action_description, plan.shot_id)
            if res["status"] == "PASS":
                print(f"✅ [Continuity Supervisor] SHOT APPROVED: {plan.shot_id}")
                dailies = state.get("scene_dailies_paths", []) + [state["current_render_path"]]
                return {
                    "scene_dailies_paths": dailies,
                    "continuity_feedback": None,
                    "current_render_path": None,
                    "current_keyframe_path": None,
                    "render_retry_count": 0
                }
        
        return {
            "continuity_feedback": res.get("feedback", "Rejected by QA"),
            "render_retry_count": state.get("render_retry_count", 0) + 1
        }
        
    return {}
