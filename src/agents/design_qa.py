from typing import Dict, List, Optional
import time
from src.agents.base import BaseQA
from src.pipeline.state import AFCState, ShotExecutionPlan
from src.agents.shared import extract_scene_id


class DesignQAAgent(BaseQA):
    def evaluate_character_design(
        self,
        image_path: str,
        entity_name: str,
        description: str,
    ) -> Dict:
        print(
            f"🔍 [Design QA] Evaluating CHARACTER design for '{entity_name}': {image_path}"
        )

        prompt = f"""Analyze this character design reference sheet for production quality.

CHARACTER: {entity_name}
EXPECTED DESCRIPTION: {description[:1000]}

Evaluation Criteria:
1. LAYOUT: The image MUST have a close-up portrait on the LEFT half AND a three-view turnaround (front, 3/4, back) on the RIGHT half. If the layout is fundamentally wrong (e.g., only a single pose, no turnaround, or no portrait), this is a FAIL.
2. NO TEXT: The image must NOT contain any text labels, dialogue bubbles, captions, watermarks, or annotations. Minor incidental text on clothing (e.g., a logo on a shirt) is acceptable, but explicit labels like "Front View" or character names are NOT.
3. DESCRIPTION MATCH: The character's appearance (face, hair, clothing, body type, age) should reasonably match the expected description. Minor artistic interpretation is acceptable.
4. CHARACTER AESTHETICS: The character must look NATURAL and appealing. Check for: exaggerated intense stares, unnaturally wide eyes, overly dramatic expressions, stiff mannequin poses, theatrical body language, forced smiles. Characters should appear relaxed and natural.
5. CLEAN BACKGROUND: The background should be white or a simple neutral tone. No complex backgrounds, no scene elements.
6. CONSISTENCY: The portrait and turnaround views should clearly depict the SAME character with consistent features across all views.

Respond with 'PASS' if the design meets production standards, or 'FAIL: [Reason]' with specific issues. Only fail for significant problems — minor stylistic variations are acceptable."""

        physical_path = self.workspace.get_physical_path(image_path)
        t0 = time.time()
        response = self.llm.analyze_image(image_path=physical_path, prompt=prompt)
        elapsed = time.time() - t0

        result_text = response.text
        print(
            f"🔍 [Design QA] Character design result ({elapsed:.1f}s): {result_text[:300]}"
        )

        log_entry = f"[DESIGN QA] CHARACTER: {entity_name}\nPATH: {image_path}\nRESULT: {result_text}\n{'-' * 40}"
        self.workspace.append_file("06_logs/qa_reports.log", log_entry)

        if "PASS" in result_text.upper() and "FAIL" not in result_text.upper():
            print(f"🔍 [Design QA] Character design ✅ PASS: {entity_name}")
            return {"status": "PASS"}

        print(f"🔍 [Design QA] Character design ❌ FAIL: {entity_name}")
        return {"status": "FAIL", "feedback": result_text}

    def evaluate_location_design(
        self,
        image_path: str,
        location_name: str,
        description: str,
    ) -> Dict:
        print(
            f"🔍 [Design QA] Evaluating LOCATION design for '{location_name}': {image_path}"
        )

        prompt = f"""Analyze this location/environment design reference sheet for production quality.

LOCATION: {location_name}
EXPECTED DESCRIPTION: {description[:1000]}

Evaluation Criteria:
1. LAYOUT: The image should show the SAME location from 3-4 different viewing directions/angles arranged in a grid or row. If only a single view is shown, this is a FAIL.
2. NO TEXT: No text labels, annotations, captions, or watermarks.
3. DESCRIPTION MATCH: The location's architecture, atmosphere, lighting, and spatial features should match the expected description.
4. NO CHARACTERS: The location design should NOT contain any human figures or characters. It is purely an environment reference.
5. SPATIAL CLARITY: Each view should clearly show distinct spatial information (e.g., front entrance, interior, side angle). Views should not be near-identical duplicates.

Respond with 'PASS' if the design meets production standards, or 'FAIL: [Reason]' with specific issues."""

        physical_path = self.workspace.get_physical_path(image_path)
        t0 = time.time()
        response = self.llm.analyze_image(image_path=physical_path, prompt=prompt)
        elapsed = time.time() - t0

        result_text = response.text
        print(
            f"🔍 [Design QA] Location design result ({elapsed:.1f}s): {result_text[:300]}"
        )

        log_entry = f"[DESIGN QA] LOCATION: {location_name}\nPATH: {image_path}\nRESULT: {result_text}\n{'-' * 40}"
        self.workspace.append_file("06_logs/qa_reports.log", log_entry)

        if "PASS" in result_text.upper() and "FAIL" not in result_text.upper():
            print(f"🔍 [Design QA] Location design ✅ PASS: {location_name}")
            return {"status": "PASS"}

        print(f"🔍 [Design QA] Location design ❌ FAIL: {location_name}")
        return {"status": "FAIL", "feedback": result_text}

    def evaluate_object_design(
        self,
        image_path: str,
        object_name: str,
        description: str,
    ) -> Dict:
        print(
            f"🔍 [Design QA] Evaluating OBJECT design for '{object_name}': {image_path}"
        )

        prompt = f"""Analyze this object/prop design reference sheet for production quality.

OBJECT: {object_name}
EXPECTED DESCRIPTION: {description[:1000]}

Evaluation Criteria:
1. LAYOUT: The image should show the object from 4-6 angles in a clean grid layout. A single view is a FAIL.
2. NO TEXT: No text labels, annotations, or watermarks.
3. DESCRIPTION MATCH: The object's shape, material, color, and details should match the expected description.
4. NO CHARACTERS: No human figures should appear in the design.
5. CLEAN BACKGROUND: White or neutral background, clean layout.

Respond with 'PASS' if the design meets production standards, or 'FAIL: [Reason]' with specific issues."""

        physical_path = self.workspace.get_physical_path(image_path)
        t0 = time.time()
        response = self.llm.analyze_image(image_path=physical_path, prompt=prompt)
        elapsed = time.time() - t0

        result_text = response.text
        print(
            f"🔍 [Design QA] Object design result ({elapsed:.1f}s): {result_text[:300]}"
        )

        log_entry = f"[DESIGN QA] OBJECT: {object_name}\nPATH: {image_path}\nRESULT: {result_text}\n{'-' * 40}"
        self.workspace.append_file("06_logs/qa_reports.log", log_entry)

        if "PASS" in result_text.upper() and "FAIL" not in result_text.upper():
            print(f"🔍 [Design QA] Object design ✅ PASS: {object_name}")
            return {"status": "PASS"}

        print(f"🔍 [Design QA] Object design ❌ FAIL: {object_name}")
        return {"status": "FAIL", "feedback": result_text}


def design_qa_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"🔍 [Design QA] === NODE ENTRY ===")
    plan = state.get("active_shot_plan")
    print(f"   active_shot_plan: {plan.shot_id if plan else None}")
    design_retry = state.get("design_retry_count", 0)
    design_feedback = state.get("design_feedback")
    print(f"   design_retry_count: {design_retry}")
    print(f"   design_feedback: {design_feedback[:100] if design_feedback else None}")
    print(f"{'=' * 60}")

    if not plan:
        print(f"🔍 [Design QA] === NODE EXIT === No plan (no-op)")
        return {}

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = DesignQAAgent.from_config(ws, state["project_config"])

    scene_id = extract_scene_id(plan.shot_id)
    novel_text = state.get("novel_text", "")

    failures = []
    total_checked = 0

    for entity in plan.active_entities:
        for prefix in [
            f"03_lore_bible/designs/scenes/{scene_id}",
            "03_lore_bible/designs",
        ]:
            path = f"{prefix}/{entity}.png"
            if not ws.exists(path):
                continue

            total_checked += 1

            entity_type = "character"
            lore_desc = ""
            try:
                lore_desc = ws.read_file(f"03_lore_bible/{entity}.md")
            except FileNotFoundError:
                pass

            if not lore_desc:
                entity_type_prompt = f"Is '{entity}' a CHARACTER or OBJECT in this context? {novel_text[:2000]}"
                try:
                    resp = agent.llm.generate_text(entity_type_prompt)
                    if "OBJECT" in resp.text.upper():
                        entity_type = "object"
                except Exception:
                    pass

            if entity_type == "character":
                result = agent.evaluate_character_design(path, entity, lore_desc[:1000])
            else:
                result = agent.evaluate_object_design(path, entity, lore_desc[:1000])

            if result["status"] != "PASS":
                failures.append(
                    f"{entity} ({path}): {result.get('feedback', 'unknown')}"
                )
            break

    if scene_id:
        scene_path = state.get("current_scene_path")
        if scene_path:
            try:
                scene_data = ws.read_json(scene_path)
                location = scene_data.get("physical_location", "")
                if location:
                    safe_name = location.replace("/", "_").replace("\\", "_")
                    for loc_prefix in [
                        f"03_lore_bible/designs/scenes/{scene_id}/locations",
                        "03_lore_bible/designs/locations",
                    ]:
                        loc_path = f"{loc_prefix}/{safe_name}.png"
                        if ws.exists(loc_path):
                            total_checked += 1
                            loc_desc = ""
                            try:
                                loc_desc = ws.read_file(
                                    f"03_lore_bible/designs/locations/{safe_name}.md"
                                )
                            except FileNotFoundError:
                                loc_desc = f"Location: {location}"

                            result = agent.evaluate_location_design(
                                loc_path, location, loc_desc[:1000]
                            )
                            if result["status"] != "PASS":
                                failures.append(
                                    f"LOCATION {location} ({loc_path}): {result.get('feedback', 'unknown')}"
                                )
                            break
            except Exception as e:
                print(f"🔍 [Design QA] ⚠️  Could not check location design: {e}")

    if total_checked == 0:
        print(f"🔍 [Design QA] No designs found to check — skipping QA")
        print(f"🔍 [Design QA] === NODE EXIT === (no designs)")
        return {"design_feedback": None, "design_retry_count": 0}

    if not failures:
        print(f"🔍 [Design QA] All {total_checked} design(s) PASSED ✅")
        print(f"🔍 [Design QA] === NODE EXIT === All designs approved")
        return {"design_feedback": None, "design_retry_count": 0}

    combined_feedback = "\n".join(failures)
    retry = design_retry + 1
    print(
        f"🔍 [Design QA] {len(failures)}/{total_checked} design(s) FAILED ❌ (retry #{retry})"
    )
    print(f"   Failures: {combined_feedback[:300]}")

    if retry >= 3:
        print(
            f"🔍 [Design QA] 🚨 Max retries reached ({retry}). Accepting designs as-is and proceeding."
        )
        print(f"🔍 [Design QA] === NODE EXIT === Max retries, force-accepting")
        return {"design_feedback": None, "design_retry_count": 0}

    print(f"🔍 [Design QA] === NODE EXIT === Requesting redesign (retry #{retry})")
    return {"design_feedback": combined_feedback, "design_retry_count": retry}
