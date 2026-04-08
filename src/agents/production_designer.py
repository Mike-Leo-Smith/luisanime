from typing import Dict, Any, List, Optional
import time
from src.agents.base import BaseCreative
from src.pipeline.state import AFCState
from src.providers.base import ImageGenerationConfig
from src.agents.prompts import PRODUCTION_DESIGNER_PROMPT
from src.agents.shared import extract_scene_id, load_master_style, load_style_preset


class ProductionDesignerAgent(BaseCreative):
    def generate_master_style(self, novel_context: str) -> str:
        """Generates a comprehensive master style description including historical era."""
        print(
            "🎨 [Production Designer] Generating master style description and identifying era..."
        )
        print(
            f"   Novel context length: {len(novel_context)} chars (using first 20000)"
        )

        style_key, _prefix, _suffix = load_style_preset(self.project_config)
        preset = self.project_config.get("style_presets", {}).get(style_key, {})
        print(f"   Style key: {style_key}")

        prompt = f"""Analyze the provided novel excerpt and determine its historical era/setting. 
Then, create a PURELY VISUAL cinematic style guide that blends this historical period with the theme: '{style_key}'.

User Style Preset: {preset.get("prompt_prefix", "")} {preset.get("prompt_suffix", "")}

Include:
1. IDENTIFIED ERA: (e.g. 19th Century France, Futuristic Cyberpunk, Ancient China)
2. VISUAL STYLE: Lighting, color palette, camera lens characteristics, and texture.
3. PERIOD DETAILS: Specific architectural or fashion cues to maintain historical/setting fidelity.

STRICT RULE: Output ONLY the descriptive guide. No conversational filler.
Keep it under 1000 characters.

Novel Excerpt:
{novel_context[:20000]}
"""

        t0 = time.time()
        response = self.llm.generate_text(
            prompt, system_prompt=PRODUCTION_DESIGNER_PROMPT
        )
        elapsed = time.time() - t0
        style_desc = response.text.replace("#", "").replace("**", "").strip()

        self.workspace.write_file("03_lore_bible/master_style.md", style_desc)
        print(
            f"🎨 [Production Designer] Master style bible established in {elapsed:.1f}s"
        )
        print(f"   Style description ({len(style_desc)} chars): {style_desc[:300]}...")
        return style_desc

    def generate_design(
        self,
        entity_name: str,
        description: str,
        master_style: str,
        scene_id: Optional[str] = None,
        reference_paths: Optional[List[str]] = None,
    ) -> str:
        print(
            f"🎨 [Production Designer] Creating visual design for: {entity_name} (scene={scene_id or 'global'})"
        )
        print(f"   Description: {description[:200]}...")
        if reference_paths:
            print(f"   Reference images: {reference_paths}")

        _style_key, prefix, suffix = load_style_preset(self.project_config)

        ref_instruction = ""
        if reference_paths:
            ref_instruction = " IMPORTANT: Match the character's overall appearance, body type, and facial features shown in the reference image(s). Adapt clothing and expression to this scene's context while maintaining the same person's identity."

        prompt = f"{prefix} A character design reference sheet on a white background for: {entity_name}. Layout: LEFT HALF shows a detailed close-up portrait (face, expression, hair, accessories); RIGHT HALF shows a three-view turnaround (front, 3/4 side, back) of the full body at the same scale. Description: {description}. Style: {suffix}. Guidelines: {master_style[:300]}.{ref_instruction} CHARACTER AESTHETICS: natural, conventionally attractive appearance. Relaxed natural expression (gentle smile or calm neutral face). Comfortable organic posture. No intense stares, exaggerated expressions, theatrical poses, or stiff mannequin stance. The character should look like a real person, not an actor performing. White background, clean layout, no text labels."

        config = ImageGenerationConfig()
        if reference_paths:
            config.reference_media = [
                self.workspace.get_physical_path(p) for p in reference_paths
            ]

        if scene_id:
            image_path = f"03_lore_bible/designs/scenes/{scene_id}/{entity_name}.png"
        else:
            image_path = f"03_lore_bible/designs/{entity_name}.png"

        self.log_prompt(
            "ProductionDesigner",
            f"DESIGN_{entity_name}",
            prompt,
            custom_path=f"{image_path}.prompt.txt",
        )

        print(
            f"🎨 [Production Designer] Image generation prompt ({len(prompt)} chars): {prompt[:300]}..."
        )
        t0 = time.time()
        response = self.image_gen.generate_image(prompt=prompt, config=config)
        elapsed = time.time() - t0

        self.workspace.save_media(image_path, response.image_bytes)
        print(
            f"🎨 [Production Designer] Design saved: {image_path} ({len(response.image_bytes)} bytes, {elapsed:.1f}s)"
        )
        return image_path

    def generate_location_design(
        self,
        location_name: str,
        description: str,
        master_style: str,
        scene_id: Optional[str] = None,
        reference_paths: Optional[List[str]] = None,
    ) -> str:
        print(
            f"🎨 [Production Designer] Creating location design for: {location_name} (scene={scene_id or 'global'})"
        )
        print(f"   Description: {description[:200]}...")
        if reference_paths:
            print(f"   Reference images: {reference_paths}")

        _style_key, prefix, suffix = load_style_preset(self.project_config)

        ref_instruction = ""
        if reference_paths:
            ref_instruction = " IMPORTANT: Match the location's architectural style, color palette, and atmosphere shown in the reference image. Adapt lighting and weather to this scene's specific moment while maintaining the same place's identity."

        prompt = f"{prefix} A multi-view environment design sheet on a white background for: {location_name}. Layout: show the same location from 3-4 different viewing directions (e.g., front entrance, interior wide, side angle, rear/opposite wall) arranged in a grid. Description: {description}. Style: {suffix}. Guidelines: {master_style[:300]}.{ref_instruction} Capture key spatial features, architecture, lighting, and atmosphere from each direction. No characters, no text labels."

        config = ImageGenerationConfig()
        if reference_paths:
            config.reference_media = [
                self.workspace.get_physical_path(p) for p in reference_paths
            ]

        safe_name = location_name.replace("/", "_").replace("\\", "_")
        if scene_id:
            image_path = (
                f"03_lore_bible/designs/scenes/{scene_id}/locations/{safe_name}.png"
            )
        else:
            image_path = f"03_lore_bible/designs/locations/{safe_name}.png"

        self.log_prompt(
            "ProductionDesigner",
            f"LOCATION_{safe_name}",
            prompt,
            custom_path=f"{image_path}.prompt.txt",
        )

        print(
            f"🎨 [Production Designer] Location prompt ({len(prompt)} chars): {prompt[:300]}..."
        )
        t0 = time.time()
        response = self.image_gen.generate_image(prompt=prompt, config=config)
        elapsed = time.time() - t0

        self.workspace.save_media(image_path, response.image_bytes)
        print(
            f"🎨 [Production Designer] Location design saved: {image_path} ({len(response.image_bytes)} bytes, {elapsed:.1f}s)"
        )
        return image_path

    def generate_object_design(
        self,
        object_name: str,
        description: str,
        master_style: str,
        scene_id: Optional[str] = None,
        reference_paths: Optional[List[str]] = None,
    ) -> str:
        print(
            f"🎨 [Production Designer] Creating OBJECT design for: {object_name} (scene={scene_id or 'global'})"
        )
        print(f"   Description: {description[:200]}...")
        if reference_paths:
            print(f"   Reference images: {reference_paths}")

        _style_key, prefix, suffix = load_style_preset(self.project_config)

        ref_instruction = ""
        if reference_paths:
            ref_instruction = " IMPORTANT: Match the object's shape, material, and details shown in the reference image(s). Adapt to this scene's context while maintaining the same object's identity."

        prompt = f"{prefix} A detailed object/prop reference sheet on a white background for: {object_name}. Layout: show the object from 4-6 angles (front, back, side, top, detail close-up) arranged in a clean grid. Description: {description}. Style: {suffix}. Guidelines: {master_style[:300]}.{ref_instruction} White background, clean layout, no text labels, no human figures."

        config = ImageGenerationConfig()
        if reference_paths:
            config.reference_media = [
                self.workspace.get_physical_path(p) for p in reference_paths
            ]

        if scene_id:
            image_path = f"03_lore_bible/designs/scenes/{scene_id}/{object_name}.png"
        else:
            image_path = f"03_lore_bible/designs/{object_name}.png"

        self.log_prompt(
            "ProductionDesigner",
            f"OBJECT_{object_name}",
            prompt,
            custom_path=f"{image_path}.prompt.txt",
        )

        print(
            f"🎨 [Production Designer] Object prompt ({len(prompt)} chars): {prompt[:300]}..."
        )
        t0 = time.time()
        response = self.image_gen.generate_image(prompt=prompt, config=config)
        elapsed = time.time() - t0

        self.workspace.save_media(image_path, response.image_bytes)
        print(
            f"🎨 [Production Designer] Object design saved: {image_path} ({len(response.image_bytes)} bytes, {elapsed:.1f}s)"
        )
        return image_path

    def classify_entity(self, entity_name: str, novel_context: str) -> str:
        """Classify an entity as 'character' or 'object' using LLM."""
        prompt = f"""Classify the entity '{entity_name}' from the novel as either a CHARACTER or an OBJECT/PROP.
- CHARACTER: a person, animal, or sentient being that acts, speaks, or has emotions.
- OBJECT: an inanimate item, prop, artifact, tool, or non-sentient thing (e.g., a watch, sword, letter, vehicle).

Novel excerpt (first 5000 chars):
{novel_context[:5000]}

Reply with EXACTLY one word: CHARACTER or OBJECT"""

        response = self.llm.generate_text(prompt)
        result = response.text.strip().upper()
        if "OBJECT" in result:
            return "object"
        return "character"


def production_designer_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"🎨 [Production Designer] === NODE ENTRY ===")
    plan = state.get("active_shot_plan")
    print(f"   active_shot_plan: {plan.shot_id if plan else None}")
    if plan:
        print(f"   active_entities: {plan.active_entities}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = ProductionDesignerAgent.from_config(ws, state["project_config"])

    # 1. Ensure Master Style exists
    try:
        master_style = ws.read_file("03_lore_bible/master_style.md")
        print(
            f"🎨 [Production Designer] Master style already exists ({len(master_style)} chars)"
        )
    except FileNotFoundError:
        print(f"🎨 [Production Designer] No master style found — generating...")
        novel_text = state.get("novel_text", "")
        master_style = agent.generate_master_style(novel_text)

    scene_id = extract_scene_id(plan.shot_id) if plan else None

    scene_path = state.get("current_scene_path")
    novel_text = state.get("novel_text", "")
    scene_data = None
    if scene_path:
        try:
            scene_data = ws.read_json(scene_path)
        except Exception as e:
            print(f"🎨 [Production Designer] ⚠️  Could not read scene: {e}")

    # 2. Generate master/global designs for active entities (character vs object)
    entity_types: Dict[str, str] = {}
    if plan:
        for entity in plan.active_entities:
            global_path = f"03_lore_bible/designs/{entity}.png"
            if not ws.exists(global_path):
                entity_type = agent.classify_entity(entity, novel_text)
                entity_types[entity] = entity_type
                print(
                    f"🎨 [Production Designer] Entity '{entity}' classified as: {entity_type}"
                )
                print(
                    f"🎨 [Production Designer] Generating MASTER design for '{entity}' ({entity_type})..."
                )

                if entity_type == "character":
                    extraction_prompt = f"""Extract a PURELY VISUAL, comprehensive physical description for the character '{entity}' as described across the entire novel.
                    Include: facial features, typical clothing style, body type, age, hair, skin tone, and any distinguishing physical traits.
                    This is a MASTER reference — describe their DEFAULT canonical appearance, not scene-specific variations.
                    STRICT RULE: Output ONLY the visual description text. No markdown headers, no conversational filler.
                    
                    Novel Text:
                    {novel_text[:50000]}
                    """
                else:
                    extraction_prompt = f"""Extract a PURELY VISUAL, comprehensive physical description for the object/prop '{entity}' as described across the entire novel.
                    Include: shape, size, material, color, texture, markings, and any distinguishing physical details.
                    This is a MASTER reference — describe the object's DEFAULT canonical appearance.
                    STRICT RULE: Output ONLY the visual description text. No markdown headers, no conversational filler.
                    
                    Novel Text:
                    {novel_text[:50000]}
                    """

                t0 = time.time()
                desc_resp = agent.llm.generate_text(
                    extraction_prompt, system_prompt=PRODUCTION_DESIGNER_PROMPT
                )
                elapsed = time.time() - t0
                clean_desc = desc_resp.text.replace("#", "").replace("**", "").strip()
                if "Visual Description:" in clean_desc:
                    clean_desc = clean_desc.split("Visual Description:")[1].strip()
                print(
                    f"🎨 [Production Designer] Master description for '{entity}' extracted in {elapsed:.1f}s: {clean_desc[:200]}..."
                )
                try:
                    if entity_type == "character":
                        agent.generate_design(entity, clean_desc[:500], master_style)
                    else:
                        agent.generate_object_design(
                            entity, clean_desc[:500], master_style
                        )
                except Exception as e:
                    print(
                        f"🎨 [Production Designer] ⚠️  Failed to generate master design for '{entity}': {e}"
                    )
            else:
                print(
                    f"🎨 [Production Designer] Master design already exists for '{entity}' — skipping"
                )

    # 3. Generate master/global location environment design
    if scene_data:
        location = scene_data.get("physical_location", "")
        if location:
            safe_name = location.replace("/", "_").replace("\\", "_")
            global_loc_path = f"03_lore_bible/designs/locations/{safe_name}.png"
            if not ws.exists(global_loc_path):
                print(
                    f"🎨 [Production Designer] Generating MASTER environment design for location '{location}'..."
                )
                extraction_prompt = f"""Extract a PURELY VISUAL description of the location '{location}' as described across the entire novel.
                Include: architectural style, interior/exterior details, typical lighting, color palette, atmosphere, and distinctive features.
                This is a MASTER reference — describe the location's canonical, default appearance (e.g. daytime, neutral weather).
                STRICT RULE: Output ONLY the visual description text. No markdown headers, no conversational filler.
                
                Novel Text:
                {novel_text[:50000]}
                """
                t0 = time.time()
                desc_resp = agent.llm.generate_text(
                    extraction_prompt, system_prompt=PRODUCTION_DESIGNER_PROMPT
                )
                elapsed = time.time() - t0
                clean_desc = desc_resp.text.replace("#", "").replace("**", "").strip()
                print(
                    f"🎨 [Production Designer] Master location '{location}' description extracted in {elapsed:.1f}s: {clean_desc[:200]}..."
                )
                try:
                    agent.generate_location_design(
                        location, clean_desc[:500], master_style
                    )
                except Exception as e:
                    print(
                        f"🎨 [Production Designer] ⚠️  Failed to generate master location design for '{location}': {e}"
                    )
            else:
                print(
                    f"🎨 [Production Designer] Master environment design already exists for '{location}' — skipping"
                )

    # 4. Generate scene-specific location design (referencing master design)
    if scene_data and scene_id:
        location = scene_data.get("physical_location", "")
        if location:
            safe_name = location.replace("/", "_").replace("\\", "_")
            scene_loc_path = (
                f"03_lore_bible/designs/scenes/{scene_id}/locations/{safe_name}.png"
            )
            if not ws.exists(scene_loc_path):
                master_loc_ref = f"03_lore_bible/designs/locations/{safe_name}.png"
                ref_paths = [master_loc_ref] if ws.exists(master_loc_ref) else None

                print(
                    f"🎨 [Production Designer] Generating scene-specific location design for '{location}' (scene={scene_id})..."
                )
                scene_context = f"Scene: {scene_data.get('scene_id', '')}. Location: {location}. Era: {scene_data.get('era_context', '')}."
                extraction_prompt = f"""Extract a PURELY VISUAL description of the location '{location}' as it appears in this specific scene.
                Include: architectural style, interior/exterior details, lighting conditions, color palette, atmosphere, and any distinctive features.
                Consider the scene context: {scene_context}
                STRICT RULE: Output ONLY the visual description text. No markdown headers, no conversational filler.
                
                Novel Text:
                {novel_text[:50000]}
                """
                t0 = time.time()
                desc_resp = agent.llm.generate_text(
                    extraction_prompt, system_prompt=PRODUCTION_DESIGNER_PROMPT
                )
                elapsed = time.time() - t0
                clean_desc = desc_resp.text.replace("#", "").replace("**", "").strip()
                print(
                    f"🎨 [Production Designer] Location '{location}' description extracted in {elapsed:.1f}s: {clean_desc[:200]}..."
                )
                try:
                    agent.generate_location_design(
                        location,
                        clean_desc[:500],
                        master_style,
                        scene_id=scene_id,
                        reference_paths=ref_paths,
                    )
                except Exception as e:
                    print(
                        f"🎨 [Production Designer] ⚠️  Failed to generate location design for '{location}': {e}"
                    )
            else:
                print(
                    f"🎨 [Production Designer] Scene location design already exists for '{location}' (scene={scene_id}) — skipping"
                )

    # 5. Generate scene-specific entity designs (referencing master sheets)
    if plan and scene_id:
        scene_context_str = ""
        if scene_data:
            scene_context_str = f"Scene location: {scene_data.get('physical_location', '')}. Era: {scene_data.get('era_context', '')}. Actions: {', '.join(scene_data.get('actions', [])[:3])}."

        for entity in plan.active_entities:
            scene_design_path = f"03_lore_bible/designs/scenes/{scene_id}/{entity}.png"
            if not ws.exists(scene_design_path):
                master_ref = f"03_lore_bible/designs/{entity}.png"
                ref_paths = [master_ref] if ws.exists(master_ref) else None

                entity_type = entity_types.get(entity)
                if entity_type is None:
                    entity_type = agent.classify_entity(entity, novel_text)
                    entity_types[entity] = entity_type

                print(
                    f"🎨 [Production Designer] Generating scene-specific design for '{entity}' ({entity_type}, scene={scene_id})..."
                )

                if entity_type == "character":
                    extraction_prompt = f"""Extract a PURELY VISUAL physical description for the character '{entity}' as they appear in this specific scene.
                    Include: facial features, clothing appropriate to the scene context, body type, age, and current emotional/physical state.
                    Scene context: {scene_context_str}
                    STRICT RULE: Output ONLY the visual description text. No markdown headers, no conversational filler, no 'As an art director...', no introductory or concluding remarks.
                    
                    Novel Text:
                    {novel_text[:50000]}
                    """
                else:
                    extraction_prompt = f"""Extract a PURELY VISUAL physical description for the object/prop '{entity}' as it appears in this specific scene.
                    Include: shape, size, material, color, texture, condition, and any scene-specific details (e.g., lighting, wear).
                    Scene context: {scene_context_str}
                    STRICT RULE: Output ONLY the visual description text. No markdown headers, no conversational filler.
                    
                    Novel Text:
                    {novel_text[:50000]}
                    """

                t0 = time.time()
                desc_resp = agent.llm.generate_text(
                    extraction_prompt, system_prompt=PRODUCTION_DESIGNER_PROMPT
                )
                elapsed = time.time() - t0

                clean_desc = desc_resp.text.replace("#", "").replace("**", "").strip()
                if "Visual Description:" in clean_desc:
                    clean_desc = clean_desc.split("Visual Description:")[1].strip()

                print(
                    f"🎨 [Production Designer] Entity '{entity}' scene description extracted in {elapsed:.1f}s: {clean_desc[:200]}..."
                )
                try:
                    if entity_type == "character":
                        agent.generate_design(
                            entity,
                            clean_desc[:500],
                            master_style,
                            scene_id=scene_id,
                            reference_paths=ref_paths,
                        )
                    else:
                        agent.generate_object_design(
                            entity,
                            clean_desc[:500],
                            master_style,
                            scene_id=scene_id,
                            reference_paths=ref_paths,
                        )
                except Exception as e:
                    print(
                        f"🎨 [Production Designer] ⚠️  Failed to generate design for '{entity}': {e}"
                    )
            else:
                print(
                    f"🎨 [Production Designer] Scene design already exists for '{entity}' (scene={scene_id}) — skipping"
                )

    print(f"🎨 [Production Designer] === NODE EXIT ===")
    return {}
