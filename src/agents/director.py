from typing import Dict, Any, List, Optional
import json
import time
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
                    "active_entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "staging_description": {"type": "STRING"},
                    "character_poses": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "entity_id": {"type": "STRING"},
                                "pose": {"type": "STRING"},
                            },
                            "required": ["entity_id", "pose"],
                        },
                    },
                    "setting_details": {"type": "STRING"},
                    "era_context": {"type": "STRING"},
                    "dialogue": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "speaker": {"type": "STRING"},
                                "line": {"type": "STRING"},
                                "emotion": {"type": "STRING"},
                            },
                            "required": ["speaker", "line", "emotion"],
                        },
                    },
                    "ending_composition_description": {"type": "STRING"},
                    "is_continuation": {"type": "BOOLEAN"},
                },
                "required": [
                    "shot_id",
                    "target_duration_ms",
                    "camera_movement",
                    "detailed_camera_plan",
                    "action_description",
                    "active_entities",
                    "staging_description",
                    "character_poses",
                    "setting_details",
                    "era_context",
                    "dialogue",
                    "ending_composition_description",
                    "is_continuation",
                ],
            },
        }
    },
    "required": ["shots"],
}


class DirectorAgent(BaseCreative):
    def parse_scene_json(self, scene_path: str) -> Dict:
        """Ingests the screenwriter's output."""
        print(f"🎬 [Director] Parsing scene: {scene_path}")
        return self.workspace.read_json(scene_path)

    def write_shot_plan(self, scene_data: Dict) -> List[ShotExecutionPlan]:
        """Outputs an array of rigid technical shot constraints with cinematic continuity."""
        scene_id = scene_data.get("scene_id", "1")
        print(f"🎬 [Director] Generating continuous shot plans for scene: {scene_id}")
        print(f"   Scene data keys: {list(scene_data.keys())}")
        print(f"   Active entities: {scene_data.get('active_entities', [])}")
        print(f"   Actions count: {len(scene_data.get('actions', []))}")

        prompt = f"""Based on the following Scene JSON, generate a sequence of technical ShotExecutionPlan JSONs.
        
        CRITICAL CONTINUITY RULE:
        The sequence must be SEAMLESS. The 'staging_description' and 'character_poses' at the START of Shot N must exactly match the 'ending_composition_description' of Shot N-1.
        Avoid 'jumps' between shots unless explicitly noted as a cut. Prefer match cuts or continuous motion.
        
        CONTINUATION MARKING RULE:
        Set 'is_continuation' to true when a shot directly continues the SAME continuous action, camera movement, or motion from the previous shot WITHOUT a cut. This means the previous shot's ending and this shot's beginning are the exact same moment in time — no time skip, no angle change, no new subject.
        Set 'is_continuation' to false when this shot starts a new camera angle, introduces a new subject, or begins a distinctly different action (even if temporally adjacent).
        The FIRST shot of a scene must ALWAYS have is_continuation=false.
        
        DIALOGUE ASSIGNMENT RULE:
        The scene contains dialogue lines. You MUST distribute these dialogue lines into the appropriate shots based on when they are spoken during the action.
        Each shot's 'dialogue' array should contain the lines spoken DURING that shot, preserving speaker, line (in original language), and emotion.
        If a shot has no dialogue, use an empty array.
        Dialogue timing should match the shot's action — a character speaking should be visible and their expression should match the emotion.
        
        STRICT RULES:
        1. Keep character names, locations, and IDs in the ORIGINAL LANGUAGE (Chinese).
        2. Era Context: Precisely determine the specific historical era or setting.
        3. Detailed Camera Plan: Specific movement from a defined START composition to a defined END composition.
        4. Staging: Specific environmental layout and character positioning.
        5. Character Poses: Vividly describe the pose and facial expression, especially reflecting the emotion of any dialogue being spoken in that shot.
        6. Ending Composition: Describe the EXACT visual state at the final millisecond of this shot.
        
        Use deterministic shot IDs: '{scene_id}_SHOT_001', '{scene_id}_SHOT_002', etc.
        
        Scene Data:
        {json.dumps(scene_data, indent=2, ensure_ascii=False)}
        """

        t0 = time.time()
        response = self.llm.generate_structured(
            prompt=prompt,
            response_schema=SHOT_LIST_SCHEMA,
            system_prompt=DIRECTOR_PROMPT,
        )
        elapsed = time.time() - t0
        print(f"🎬 [Director] LLM returned in {elapsed:.1f}s")

        shots = []
        for i, shot_data in enumerate(response.get("shots", []), 1):
            shot_data["shot_id"] = f"{scene_id}_SHOT_{i:03d}"
            if i == 1:
                shot_data["is_continuation"] = False

            # Convert list of poses back to dict
            poses_list = shot_data.get("character_poses", [])
            poses_dict = {p["entity_id"]: p["pose"] for p in poses_list}
            shot_data["character_poses"] = poses_dict

            dialogue = shot_data.get("dialogue", [])
            shot_data["dialogue"] = [
                {
                    "speaker": d.get("speaker", ""),
                    "line": d.get("line", ""),
                    "emotion": d.get("emotion", ""),
                }
                for d in dialogue
            ]

            shot = ShotExecutionPlan(**shot_data)
            shots.append(shot)

            # Save EACH shot to its own file
            shot_file = f"04_production_slate/shots/{shot.shot_id}.json"
            self.workspace.write_json(shot_file, shot_data)

            dialogue_count = len(shot_data["dialogue"])
            print(
                f"   🎞️ {shot.shot_id}: {shot.camera_movement} | duration={shot.target_duration_ms}ms | entities={shot.active_entities} | continuation={shot.is_continuation} | dialogue={dialogue_count} lines"
            )

        print(
            f"🎬 [Director] Created {len(shots)} continuous shots. Saved individually."
        )
        return shots


def director_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"🎬 [Director] === NODE ENTRY ===")
    current_scene = state.get("current_scene_path")
    unprocessed = state.get("unprocessed_scenes", [])
    print(f"   current_scene_path: {current_scene}")
    print(f"   unprocessed_scenes: {len(unprocessed)} — {unprocessed}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = DirectorAgent.from_config(ws, state["project_config"])

    current_scene_path = state.get("current_scene_path")
    if not current_scene_path:
        if state.get("unprocessed_scenes"):
            current_scene_path = state["unprocessed_scenes"][0]
            print(f"🎬 [Director] Picked first unprocessed scene: {current_scene_path}")
        else:
            print(f"🎬 [Director] === NODE EXIT === No scenes — escalating")
            return {"escalation_required": True}

    scene_data = agent.parse_scene_json(current_scene_path)
    print(
        f"🎬 [Director] Scene data loaded: {json.dumps(scene_data, indent=2, ensure_ascii=False)[:500]}..."
    )
    shots = agent.write_shot_plan(scene_data)

    unprocessed_scenes = state.get("unprocessed_scenes", [])
    if current_scene_path in unprocessed_scenes:
        unprocessed_scenes.remove(current_scene_path)

    print(
        f"🎬 [Director] === NODE EXIT === {len(shots)} shots created, {len(unprocessed_scenes)} scenes remaining"
    )
    return {
        "current_scene_path": current_scene_path,
        "unprocessed_scenes": unprocessed_scenes,
        "unprocessed_shots": shots,
        "escalation_required": False,
    }
