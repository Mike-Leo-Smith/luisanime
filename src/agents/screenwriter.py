from typing import Dict, Any, List, Optional
from src.agents.base import BaseCreative
from src.pipeline.state import AFCState
from src.agents.prompts import SCREENWRITER_PROMPT

SCENE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "scenes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "scene_id": {"type": "STRING"},
                    "temporal_marker": {"type": "STRING"},
                    "physical_location": {"type": "STRING"},
                    "era_context": {"type": "STRING"}, # Added for transmigration/time-travel support
                    "active_entities": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "actions": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["scene_id", "temporal_marker", "physical_location", "active_entities", "actions"]
            }
        }
    },
    "required": ["scenes"]
}

class ScreenwriterAgent(BaseCreative):
    def parse_source_text(self, text_chunk: str) -> List[Dict]:
        """Extracts dialogue, action, and setting into discrete events."""
        print(f"✍️ [Screenwriter] Analyzing source text (length: {len(text_chunk)} characters)...")
        prompt = f"Analyze the following prose and translate it into chronologically ordered JSON scene documents:\n\n{text_chunk}"
        
        response = self.llm.generate_structured(
            prompt=prompt,
            response_schema=SCENE_SCHEMA,
            system_prompt=SCREENWRITER_PROMPT
        )
        scenes = response.get("scenes", [])
        print(f"✍️ [Screenwriter] Generated {len(scenes)} scenes.")
        return scenes
        
    def write_scene_file(self, scene_data: Dict) -> str:
        """Commits the structured scene breakdown to the workspace."""
        path = f"02_screenplays/{scene_data['scene_id']}.json"
        print(f"✍️ [Screenwriter] Writing scene file: {path}")
        self.workspace.write_json(path, scene_data)
        return path

def screenwriter_node(state: AFCState) -> Dict:
    from src.pipeline.workspace import AgenticWorkspace
    ws = AgenticWorkspace(state["workspace_root"])
    agent = ScreenwriterAgent.from_config(ws, state["project_config"])
    
    # Read source material
    text = ws.read_file("01_source_material/novel.txt")
    scenes = agent.parse_source_text(text)
    
    scene_paths = []
    for s in scenes:
        path = agent.write_scene_file(s)
        scene_paths.append(path)
        
    return {
        "unprocessed_scenes": scene_paths
    }
