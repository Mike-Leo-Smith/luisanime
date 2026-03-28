from typing import Dict, Any, List, Optional
import json
from src.agents.base import BaseCreative
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.agents.prompts import DIRECTOR_PROMPT

# Expanded schema for Director to include continuity linkage
SHOT_LIST_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "shots": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "shot_id": {"type": "STRING"},
                    "target_duration_ms": {"type": "INTEGER"},
                    "camera_movement": {"type": "STRING"},
                    "detailed_camera_plan": {"type": "STRING"},
                    "action_description": {"type": "STRING"},
                    "active_entities": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "staging_description": {"type": "STRING"},
                    "character_poses": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "entity_id": {"type": "STRING"},
                                "pose": {"type": "STRING"}
                            },
                            "required": ["entity_id", "pose"]
                        }
                    },
                    "setting_details": {"type": "STRING"},
                    "era_context": {"type": "STRING"},
                    "ending_composition_description": {"type": "STRING"}
                },
                "required": [
                    "shot_id", "target_duration_ms", "camera_movement", "detailed_camera_plan",
                    "action_description", "active_entities", 
                    "staging_description", "character_poses", "setting_details", "era_context",
                    "ending_composition_description"
                ]
            }
        }
    },
    "required": ["shots"]
}

class DirectorAgent(BaseCreative):
    def parse_scene_json(self, scene_path: str) -> Dict:
        """Ingests the screenwriter's output."""
        print(f"🎬 [Director] Parsing scene: {scene_path}")
        return self.workspace.read_json(scene_path)
        
    def write_shot_plan(self, scene_data: Dict) -> List[ShotExecutionPlan]:
        """Outputs an array of rigid technical shot constraints with cinematic continuity."""
        scene_id = scene_data.get('scene_id', '1')
        print(f"🎬 [Director] Generating continuous shot plans for scene: {scene_id}")
        
        prompt = f"""Based on the following Scene JSON, generate a sequence of technical ShotExecutionPlan JSONs.
        
        CRITICAL CONTINUITY RULE:
        The sequence must be SEAMLESS. The 'staging_description' and 'character_poses' at the START of Shot N must exactly match the 'ending_composition_description' of Shot N-1.
        Avoid 'jumps' between shots unless explicitly noted as a cut. Prefer match cuts or continuous motion.
        
        STRICT RULES:
        1. Keep character names, locations, and IDs in the ORIGINAL LANGUAGE (Chinese).
        2. Era Context: Precisely determine the specific historical era or setting.
        3. Detailed Camera Plan: Specific movement from a defined START composition to a defined END composition.
        4. Staging: Specific environmental layout and character positioning.
        5. Character Poses: Vividly describe the pose and facial expression.
        6. Ending Composition: Describe the EXACT visual state at the final millisecond of this shot.
        
        Use deterministic shot IDs: 'S{scene_id}_SHOT_001', 'S{scene_id}_SHOT_002', etc.
        
        Scene Data:
        {json.dumps(scene_data, indent=2, ensure_ascii=False)}
        """
        
        response = self.llm.generate_structured(
            prompt=prompt,
            response_schema=SHOT_LIST_SCHEMA,
            system_prompt=DIRECTOR_PROMPT
        )
        
        shots = []
        for shot_data in response.get("shots", []):
            # Enforce the 'S' prefix if the LLM missed it
            if not shot_data["shot_id"].startswith("S"):
                shot_data["shot_id"] = f"S{shot_data['shot_id']}"

            # Convert list of poses back to dict
            poses_list = shot_data.get("character_poses", [])
            poses_dict = {p["entity_id"]: p["pose"] for p in poses_list}
            shot_data["character_poses"] = poses_dict
            
            shot = ShotExecutionPlan(**shot_data)
            shots.append(shot)
            
            # Save EACH shot to its own file
            shot_file = f"04_production_slate/shots/{shot.shot_id}.json"
            self.workspace.write_json(shot_file, shot_data)
            
        print(f"🎬 [Director] Created {len(shots)} continuous shots. Saved individually.")
        return shots

def director_node(state: AFCState) -> Dict:
    from src.pipeline.workspace import AgenticWorkspace
    ws = AgenticWorkspace(state["workspace_root"])
    agent = DirectorAgent.from_config(ws, state["project_config"])
    
    current_scene_path = state.get("current_scene_path")
    if not current_scene_path:
        if state.get("unprocessed_scenes"):
            current_scene_path = state["unprocessed_scenes"][0]
        else:
            return {"escalation_required": True}
            
    scene_data = agent.parse_scene_json(current_scene_path)
    shots = agent.write_shot_plan(scene_data)
    
    unprocessed_scenes = state.get("unprocessed_scenes", [])
    if current_scene_path in unprocessed_scenes:
        unprocessed_scenes.remove(current_scene_path)
    
    return {
        "current_scene_path": current_scene_path,
        "unprocessed_scenes": unprocessed_scenes,
        "unprocessed_shots": shots,
        "escalation_required": False
    }
