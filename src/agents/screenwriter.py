from typing import Dict, Any, List, Optional
import json
import time
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
                    "era_context": {
                        "type": "STRING"
                    },  # Added for transmigration/time-travel support
                    "active_entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "actions": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "dialogue": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "speaker": {"type": "STRING"},
                                "line": {"type": "STRING"},
                                "emotion": {"type": "STRING"},
                                "action_index": {"type": "INTEGER"},
                            },
                            "required": ["speaker", "line", "emotion", "action_index"],
                        },
                    },
                },
                "required": [
                    "scene_id",
                    "temporal_marker",
                    "physical_location",
                    "active_entities",
                    "actions",
                    "dialogue",
                ],
            },
        }
    },
    "required": ["scenes"],
}


class ScreenwriterAgent(BaseCreative):
    def parse_source_text(self, text_chunk: str) -> List[Dict]:
        """Extracts dialogue, action, and setting into discrete events."""
        print(f"\n{'─' * 60}")
        print(
            f"✍️ [Screenwriter] Analyzing source text (length: {len(text_chunk)} characters)..."
        )
        t0 = time.time()
        prompt = f"Analyze the following prose and translate it into chronologically ordered JSON scene documents:\n\n{text_chunk}"

        response = self.llm.generate_structured(
            prompt=prompt,
            response_schema=SCENE_SCHEMA,
            system_prompt=SCREENWRITER_PROMPT,
        )
        elapsed = time.time() - t0
        scenes = response.get("scenes", [])
        print(f"✍️ [Screenwriter] LLM returned {len(scenes)} scenes in {elapsed:.1f}s")
        for i, s in enumerate(scenes):
            dialogue_count = len(s.get("dialogue", []))
            print(
                f"   Scene {i + 1}: id={s.get('scene_id')} | location={s.get('physical_location')} | entities={s.get('active_entities')} | actions={len(s.get('actions', []))} actions | dialogue={dialogue_count} lines"
            )
        print(f"{'─' * 60}\n")
        return scenes

    def write_scene_file(self, scene_data: Dict) -> str:
        """Commits the structured scene breakdown to the workspace."""
        path = f"02_screenplays/{scene_data['scene_id']}.json"
        print(f"✍️ [Screenwriter] Writing scene file: {path}")
        self.workspace.write_json(path, scene_data)
        return path


def screenwriter_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"✍️ [Screenwriter] === NODE ENTRY ===")
    print(f"   workspace_root: {state['workspace_root']}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = ScreenwriterAgent.from_config(ws, state["project_config"])

    # Read source material
    text = ws.read_file("01_source_material/novel.txt")
    print(f"✍️ [Screenwriter] Read source material: {len(text)} chars")
    scenes = agent.parse_source_text(text)

    # Normalize scene_id to deterministic 'scene_{nn}' format
    for i, s in enumerate(scenes, 1):
        s["scene_id"] = f"scene_{i:02d}"

    scene_paths = []
    for s in scenes:
        path = agent.write_scene_file(s)
        scene_paths.append(path)

    print(f"✍️ [Screenwriter] === NODE EXIT === Output: {len(scene_paths)} scene files")
    for p in scene_paths:
        print(f"   📄 {p}")

    return {"unprocessed_scenes": scene_paths}
