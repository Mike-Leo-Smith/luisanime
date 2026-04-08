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

        prompt = f"""Based on the following Scene JSON, generate a sequence of technical ShotExecutionPlan JSONs for an AI短剧 (AI-generated short drama).
        
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
        
        --- AI短剧 FAST-CUT RULES (CRITICAL) ---
        
        AI短剧 demands EXTREME visual rhythm with rapid cuts. Follow these rules:
        
        a) DEFAULT DURATION IS 5 SECONDS: Most shots should use target_duration_ms=5000. This creates the fast-cut rhythm essential for AI短剧. Only use 10s for shots with extended dialogue (2+ lines) or complex multi-character choreography.
        b) EVERY SHOT MUST HAVE AN EXPLICIT CAMERA SPECIFICATION: shot_scale (全景/近景/特写) and camera_angle are MANDATORY. The AI video model cannot shoot without these — it needs concrete visual instructions, not vague descriptions.
        c) ACTION DESCRIPTIONS MUST BE VISUALLY CONCRETE: Write for AI generation, not for human actors. 
           WRONG: "角色表现出悲伤" / "he looks angry"
           RIGHT: "角色低下头，双手攥紧衣角，肩膀微微颤抖" / "he slams his palm on the desk, jaw clenched, nostrils flaring"
           Every action must describe OBSERVABLE physical movement that the AI can render frame-by-frame.
        d) VO WITH FAST VISUALS: For exposition-heavy moments, prefer VO (voiceover) accompanied by rapid visual montage cuts rather than long static dialogue shots. Minimize consecutive OS (on-screen dialogue) shots — too much talking-head footage makes AI output stiff.
        e) SCENE HOOK: The LAST shot of the scene MUST serve as a dramatic hook — cliffhanger, reveal, or unanswered question.
        f) ATMOSPHERE IN EVERY SHOT: The setting_details field must specify lighting (direction, quality, color temperature), color tone/palette, and any atmospheric effects (rain, fog, dust, steam). The AI video model renders ONLY what you describe.
        
        CINEMATIC FLUIDITY RULES:
        1. EFFICIENT NARRATIVE COVERAGE: Cover all KEY story beats and emotional turning points, but do NOT mechanically create one shot per action. Multiple small actions can be combined into a single shot with camera movement or staging changes. Use cinematographic techniques (establishing shots, push-ins, pans, background/foreground layering) to convey information efficiently. Prioritize FLOW and RHYTHM over exhaustive coverage. A scene with 6 tight, well-paced shots is better than 12 redundant ones.
        2. SMOOTH TRANSITIONS: Plan how each shot visually connects to the next. Use match cuts, continuous pans, or cut-on-action — avoid static-to-static jumps.
        3. PACING: DEFAULT to target_duration_ms=5000 (fast cuts). Only use target_duration_ms=10000 for shots with 2+ dialogue lines or complex multi-character choreography. Never pack more than 2 distinct movements into one shot.
        4. SHOT VARIETY (FAST-CUT RHYTHM): Alternate AGGRESSIVELY between wide, medium, and close-up shots. Do not use the same scale for 3+ consecutive shots. Use extreme close-ups for dramatic punctuation (clenched fists, widening eyes, trembling lips).
        5. MOTION: Every shot must contain visible motion — at minimum a subtle camera movement (slow dolly, gentle pan) or character micro-action (breathing, shifting weight, blinking). Fully static shots produce poor video output.
        6. SPATIAL MAP: Maintain consistent character positions and object placement. If a character is on the left, they stay on the left unless they visibly walk to the right.
        7. ENDING COMPOSITION: The 'ending_composition_description' is CRITICAL — downstream agents use it to generate the next shot's starting frame. Describe the exact visual state: character positions, expressions, camera framing, lighting.
        
        --- EDITING LOGIC (MANDATORY FOR EVERY SHOT) ---
        
        8. SHOT SCALE (shot_scale field): Set to exactly one of: extreme_wide, wide, medium, close, extreme_close.
           Scale ordering: extreme_wide=1, wide=2, medium=3, close=4, extreme_close=5.
           RULE: |shot_scale_N - shot_scale_N+1| >= 2. Consecutive shots MUST jump at least 2 levels.
           Example: wide → close (OK, jump=2), medium → close (BAD, jump=1), extreme_wide → medium (OK, jump=2).
        
        9. CAMERA ANGLE (camera_angle field): Describe the camera's vertical angle and horizontal position relative to the subject.
           Format: "[vertical]-angle [horizontal]" (e.g., "eye-level frontal", "low-angle 45-degree side", "high-angle over-shoulder", "bird's-eye overhead").
           30-DEGREE RULE: If consecutive shots show the SAME subject, camera_angle must shift by >30 degrees to avoid jump cuts.
        
        10. SPATIAL COMPOSITION (spatial_composition object — REQUIRED for every shot):
            Plan explicit depth layers to create 3D perception:
            - framing_type: dominant strategy (foreground_framing, depth_separation, leading_lines, negative_space, chiaroscuro, silhouette, standard)
            - foreground_element: what's in the extreme foreground (blurred objects, shoulders, plants, architectural elements). Use "none" only for extreme_wide establishing shots.
            - midground_subject: the primary subject with their action/pose
            - background_element: environmental context behind the subject
            - depth_of_field: lens/focus (e.g., "shallow f/1.4 bokeh", "deep f/16 all-in-focus", "rack focus FG→MG")
            - composition_technique: one of foreground_framing, depth_of_field_separation, leading_lines, negative_space, chiaroscuro, rule_of_thirds, over_shoulder, dutch_angle
        
        STRICT RULES:
        1. Keep character names, locations, and IDs in the ORIGINAL LANGUAGE (Chinese).
        2. Era Context: Precisely determine the specific historical era or setting.
        3. Detailed Camera Plan: Specific movement from a defined START composition to a defined END composition.
        4. Staging: Specific environmental layout and character positioning.
        5. Character Poses: Vividly describe the pose and facial expression using PHYSICAL descriptors (furrowed brow, clenched jaw, widened eyes), not emotional labels. Especially reflect the emotion of any dialogue being spoken in that shot.
        6. Ending Composition: Describe the EXACT visual state at the final millisecond of this shot.
        7. Setting Details: MUST include lighting (direction, quality, color temperature), color tone/palette, and atmospheric effects.
        
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
