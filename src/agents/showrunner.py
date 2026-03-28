from typing import Dict, Any, List, Optional
from src.agents.base import BaseOrchestrator
from src.pipeline.state import AFCState

class ShowrunnerAgent(BaseOrchestrator):
    def route_macro_flow(self, state: AFCState) -> str:
        """Determines the next macro state transition based on unprocessed scenes."""
        if not state.get("unprocessed_scenes"):
            print("🎬 [Showrunner] No more scenes to process. Production complete.")
            return "end"
        if state.get("escalation_required"):
            print("🎬 [Showrunner] Escalation required. Routing to Director for complexity reduction.")
            return "director"
        print(f"🎬 [Showrunner] Processing next scene. Remaining: {len(state.get('unprocessed_scenes'))}")
        return "director"
        
    def audit_ledger(self, state: AFCState) -> bool:
        """Evaluates accumulated costs against the project budget."""
        ledger = state.get("ledger")
        print(f"💰 [Showrunner] Budget Audit: ${ledger.accumulated_cost_usd:.2f} / ${ledger.project_budget_usd:.2f}")
        if ledger.accumulated_cost_usd >= ledger.project_budget_usd:
            return False
        return True

def showrunner_node(state: AFCState) -> Dict:
    from src.pipeline.workspace import AgenticWorkspace
    ws = AgenticWorkspace(state["workspace_root"])
    agent = ShowrunnerAgent.from_config(ws, state["project_config"])
    
    if not agent.audit_ledger(state):
        print("🚨 [Showrunner] HALT PRODUCTION: Budget exceeded!")
        return {"escalation_required": True}
        
    return {}
