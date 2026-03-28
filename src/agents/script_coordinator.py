from typing import Dict, Any, List, Optional
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
                    "new_state": {"type": "STRING"}
                },
                "required": ["entity_id", "new_state"]
            }
        }
    },
    "required": ["mutations"]
}

class ScriptCoordinatorAgent(BaseState):
    def track_narrative_state(self, action_description: str, active_entities: List[str]) -> List[Dict]:
        """Identifies state mutations (e.g., injuries, prop destruction)."""
        print(f"📖 [Script Coordinator] Tracking state for {active_entities}...")
        prompt = f"Identify any state changes for these entities: {active_entities} based on this action: '{action_description}'"
        
        response = self.llm.generate_structured(
            prompt=prompt,
            response_schema=MUTATION_SCHEMA,
            system_prompt=SCRIPT_COORDINATOR_PROMPT
        )
        muts = response.get("mutations", [])
        print(f"📖 [Script Coordinator] Found {len(muts)} mutations.")
        return muts
        
    def update_lore_bible(self, entity_id: str, new_state: str) -> bool:
        """Overwrites the markdown profile of an entity in the workspace."""
        path = f"03_lore_bible/{entity_id}.md"
        print(f"📖 [Script Coordinator] Updating Lore Bible: {entity_id} -> {new_state}")
        content = f"# {entity_id}\n\nLatest State: {new_state}"
        self.workspace.write_file(path, content)
        return True

def script_coordinator_node(state: AFCState) -> Dict:
    from src.pipeline.workspace import AgenticWorkspace
    ws = AgenticWorkspace(state["workspace_root"])
    agent = ScriptCoordinatorAgent.from_config(ws, state["project_config"])
    
    unprocessed_shots = state.get("unprocessed_shots", [])
    if not unprocessed_shots:
        print("📖 [Script Coordinator] End of shot list for this scene.")
        return {"active_shot_plan": None}
    
    active_shot_plan = unprocessed_shots[0]
    print(f"📖 [Script Coordinator] Setting active shot: {active_shot_plan.shot_id}")
    
    # Identify and apply mutations
    mutations = agent.track_narrative_state(
        active_shot_plan.action_description, 
        active_shot_plan.active_entities
    )
    for mut in mutations:
        agent.update_lore_bible(mut["entity_id"], mut["new_state"])
        
    return {
        "active_shot_plan": active_shot_plan,
        "unprocessed_shots": unprocessed_shots[1:]
    }
