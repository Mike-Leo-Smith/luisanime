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
                    "shot_scale": {"type": "STRING"},
                    "camera_angle": {"type": "STRING"},
                    "spatial_composition": {
                        "type": "OBJECT",
                        "properties": {
                            "framing_type": {"type": "STRING"},
                            "foreground_element": {"type": "STRING"},
                            "midground_subject": {"type": "STRING"},
                            "background_element": {"type": "STRING"},
                            "depth_of_field": {"type": "STRING"},
                            "composition_technique": {"type": "STRING"},
                        },
                        "required": [
                            "framing_type",
                            "foreground_element",
                            "midground_subject",
                            "background_element",
                            "depth_of_field",
                            "composition_technique",
                        ],
                    },
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
                    "shot_scale",
                    "camera_angle",
                    "spatial_composition",
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

        prompt = f"""Generate ShotExecutionPlan JSONs for the following scene. Apply ALL rules from your system prompt.

CONTINUITY RULE:
The sequence must be SEAMLESS. staging_description and character_poses at the START of Shot N must match ending_composition_description of Shot N-1.

CONTINUATION MARKING:
- is_continuation=true: shot continues the SAME action/camera movement from previous shot without a cut (same moment in time, no angle change, no new subject).
- is_continuation=false: new angle, new subject, or new action.
- First shot of scene: ALWAYS is_continuation=false.

DIALOGUE ASSIGNMENT:
Distribute scene dialogue into shots based on when lines are spoken. Each shot's dialogue array contains lines spoken DURING that shot (speaker, line in original language, emotion). Empty array if no dialogue.

ADDITIONAL REMINDERS:
- Ending composition is CRITICAL — downstream agents use it to generate next shot's starting frame.
- Character poses: use PHYSICAL descriptors (furrowed brow, clenched jaw), not emotional labels.
- Era context: determine the specific historical era or setting.

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
        # Shot scale ordering for validation
        _SCALE_ORDER = {
            "extreme_wide": 1,
            "wide": 2,
            "medium": 3,
            "close": 4,
            "extreme_close": 5,
        }
        prev_scale = None
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

            shot_data.setdefault("shot_scale", "")
            shot_data.setdefault("camera_angle", "")
            spatial = shot_data.get("spatial_composition", {})
            if isinstance(spatial, dict):
                shot_data["spatial_composition"] = {
                    "framing_type": spatial.get("framing_type", ""),
                    "foreground_element": spatial.get("foreground_element", ""),
                    "midground_subject": spatial.get("midground_subject", ""),
                    "background_element": spatial.get("background_element", ""),
                    "depth_of_field": spatial.get("depth_of_field", ""),
                    "composition_technique": spatial.get("composition_technique", ""),
                }
            else:
                shot_data["spatial_composition"] = {}

            shot = ShotExecutionPlan(**shot_data)
            shots.append(shot)

            # Save EACH shot to its own file
            shot_file = f"04_production_slate/shots/{shot.shot_id}.json"
            self.workspace.write_json(shot_file, shot_data)

            dialogue_count = len(shot_data["dialogue"])
            print(
                f"   🎞️ {shot.shot_id}: {shot.camera_movement} | scale={shot.shot_scale} | angle={shot.camera_angle} | duration={shot.target_duration_ms}ms | entities={shot.active_entities} | continuation={shot.is_continuation} | dialogue={dialogue_count} lines"
            )

            cur_scale = _SCALE_ORDER.get(shot.shot_scale, 0)
            if prev_scale is not None and cur_scale > 0 and prev_scale > 0:
                jump = abs(cur_scale - prev_scale)
                if jump < 2:
                    print(
                        f"   ⚠️  Shot scale jump {prev_scale}→{cur_scale} (jump={jump}) violates ≥2 rule"
                    )
            if cur_scale > 0:
                prev_scale = cur_scale

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

    unprocessed_scenes = [
        s for s in state.get("unprocessed_scenes", []) if s != current_scene_path
    ]

    print(
        f"🎬 [Director] === NODE EXIT === {len(shots)} shots created, {len(unprocessed_scenes)} scenes remaining"
    )
    return {
        "current_scene_path": current_scene_path,
        "unprocessed_scenes": unprocessed_scenes,
        "unprocessed_shots": shots,
        "escalation_required": False,
    }
