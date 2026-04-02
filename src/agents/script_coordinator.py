from typing import Dict, Any, List, Optional
import json
import time
from src.agents.base import BaseState
from src.pipeline.state import AFCState
from src.agents.prompts import SCRIPT_COORDINATOR_PROMPT

MUTATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "mutations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "entity_id": {"type": "STRING"},
                    "new_state": {"type": "STRING"},
                },
                "required": ["entity_id", "new_state"],
            },
        }
    },
    "required": ["mutations"],
}


class ScriptCoordinatorAgent(BaseState):
    def track_narrative_state(
        self, action_description: str, active_entities: List[str]
    ) -> List[Dict]:
        """Identifies state mutations (e.g., injuries, prop destruction)."""
        print(f"📖 [Script Coordinator] Tracking state for {active_entities}...")
        print(f"   Action: {action_description[:200]}")
        t0 = time.time()
        prompt = f"Identify any state changes for these entities: {active_entities} based on this action: '{action_description}'"

        response = self.llm.generate_structured(
            prompt=prompt,
            response_schema=MUTATION_SCHEMA,
            system_prompt=SCRIPT_COORDINATOR_PROMPT,
        )
        elapsed = time.time() - t0
        muts = response.get("mutations", [])
        print(
            f"📖 [Script Coordinator] LLM returned {len(muts)} mutations in {elapsed:.1f}s"
        )
        for m in muts:
            print(f"   🔄 {m.get('entity_id')}: {m.get('new_state')}")
        return muts

    def update_lore_bible(self, entity_id: str, new_state: str) -> bool:
        path = f"03_lore_bible/{entity_id}.md"
        print(
            f"📖 [Script Coordinator] Updating Lore Bible: {entity_id} -> {new_state}"
        )
        try:
            existing = self.workspace.read_file(path)
        except (FileNotFoundError, Exception):
            existing = ""

        state_section_header = "\n\n## Narrative State Updates\n"
        if "## Narrative State Updates" not in existing:
            existing += state_section_header

        import datetime

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        existing += f"\n- [{timestamp}] {new_state}"

        self.workspace.write_file(path, existing)
        return True


def script_coordinator_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"📖 [Script Coordinator] === NODE ENTRY ===")
    unprocessed_shots = state.get("unprocessed_shots", [])
    active = state.get("active_shot_plan")
    print(f"   unprocessed_shots: {len(unprocessed_shots)}")
    print(f"   current active_shot_plan: {active.shot_id if active else None}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = ScriptCoordinatorAgent.from_config(ws, state["project_config"])

    if not unprocessed_shots:
        print("📖 [Script Coordinator] End of shot list for this scene.")
        print(f"📖 [Script Coordinator] === NODE EXIT === active_shot_plan=None (done)")
        return {
            "active_shot_plan": None,
            "current_render_path": None,
            "current_keyframe_path": None,
            "current_proxy_path": None,
            "continuity_feedback": None,
            "render_retry_count": 0,
            "keyframe_retry_count": 0,
            "keyframe_is_reused_frame": False,
        }

    active_shot_plan = unprocessed_shots[0]
    remaining = unprocessed_shots[1:]
    print(f"📖 [Script Coordinator] Setting active shot: {active_shot_plan.shot_id}")
    print(f"   Remaining after this: {len(remaining)} shots")

    # Identify and apply mutations
    mutations = agent.track_narrative_state(
        active_shot_plan.action_description, active_shot_plan.active_entities
    )
    for mut in mutations:
        agent.update_lore_bible(mut["entity_id"], mut["new_state"])

    print(
        f"📖 [Script Coordinator] === NODE EXIT === active={active_shot_plan.shot_id}, {len(remaining)} queued"
    )
    return {
        "active_shot_plan": active_shot_plan,
        "unprocessed_shots": remaining,
        "current_render_path": None,
        "current_keyframe_path": None,
        "current_proxy_path": None,
        "continuity_feedback": None,
        "render_retry_count": 0,
        "keyframe_retry_count": 0,
        "keyframe_is_reused_frame": False,
    }
