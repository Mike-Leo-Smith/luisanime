from typing import Dict, Any, List, Optional
from src.agents.base import BaseOrchestrator
from src.pipeline.state import AFCState


class ShowrunnerAgent(BaseOrchestrator):
    def audit_ledger(self, state: AFCState) -> bool:
        """Evaluates accumulated costs against the project budget."""
        ledger = state.get("ledger")
        print(
            f"💰 [Showrunner] Budget Audit: ${ledger.accumulated_cost_usd:.2f} / ${ledger.project_budget_usd:.2f}"
        )
        if ledger.accumulated_cost_usd >= ledger.project_budget_usd:
            return False
        return True


def showrunner_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"🎬 [Showrunner] === NODE ENTRY ===")
    unprocessed = state.get("unprocessed_scenes", [])
    escalation = state.get("escalation_required", False)
    completed = state.get("completed_scenes_paths", [])
    print(f"   unprocessed_scenes: {len(unprocessed)}")
    print(f"   completed_scenes: {len(completed)}")
    print(f"   escalation_required: {escalation}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = ShowrunnerAgent.from_config(ws, state["project_config"])

    if not agent.audit_ledger(state):
        print("🚨 [Showrunner] HALT PRODUCTION: Budget exceeded!")
        print(f"🎬 [Showrunner] === NODE EXIT === Output: escalation_required=True")
        return {"escalation_required": True}

    print(f"🎬 [Showrunner] === NODE EXIT === Budget OK, continuing")
    return {}
