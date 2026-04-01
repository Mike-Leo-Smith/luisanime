from typing import Dict, Any, List, Optional
import time
from src.agents.base import BaseCreative
from src.pipeline.state import AFCState
from src.providers.base import ImageGenerationConfig
from src.agents.prompts import PRODUCTION_DESIGNER_PROMPT


class ProductionDesignerAgent(BaseCreative):
    def generate_master_style(self, novel_context: str) -> str:
        """Generates a comprehensive master style description including historical era."""
        print(
            "🎨 [Production Designer] Generating master style description and identifying era..."
        )
        print(
            f"   Novel context length: {len(novel_context)} chars (using first 20000)"
        )

        style_key = self.project_config.get("video", {}).get("style", "cinematic")
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
        self, entity_name: str, description: str, master_style: str
    ) -> str:
        """Generates a locked visual reference image for an entity obeying master style."""
        print(f"🎨 [Production Designer] Creating visual design for: {entity_name}")
        print(f"   Description: {description[:200]}...")

        style_key = self.project_config.get("video", {}).get("style", "cinematic")
        preset = self.project_config.get("style_presets", {}).get(style_key, {})
        prefix = preset.get("prompt_prefix", "")
        suffix = preset.get("prompt_suffix", "")

        prompt = f"{prefix} A high-quality concept art character/environment design sheet. Subject: {entity_name}. Description: {description}. Style: {suffix}. Consistent artistic look following these guidelines: {master_style[:300]}. White background, clear details, single focus."

        if len(prompt) > 1400:
            prompt = prompt[:1400]

        config = ImageGenerationConfig()
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
        self, location_name: str, description: str, master_style: str
    ) -> str:
        print(f"🎨 [Production Designer] Creating location design for: {location_name}")
        print(f"   Description: {description[:200]}...")

        style_key = self.project_config.get("video", {}).get("style", "cinematic")
        preset = self.project_config.get("style_presets", {}).get(style_key, {})
        prefix = preset.get("prompt_prefix", "")
        suffix = preset.get("prompt_suffix", "")

        prompt = f"{prefix} A high-quality cinematic concept art of a location/environment. Location: {location_name}. Description: {description}. Style: {suffix}. Consistent artistic look following these guidelines: {master_style[:300]}. Wide establishing shot, detailed architecture and atmosphere, no characters."

        if len(prompt) > 1400:
            prompt = prompt[:1400]

        config = ImageGenerationConfig()
        safe_name = location_name.replace("/", "_").replace("\\", "_")
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
    except:
        print(f"🎨 [Production Designer] No master style found — generating...")
        novel_text = state.get("novel_text", "")
        master_style = agent.generate_master_style(novel_text)

    # 2. Generate location design from scene data
    scene_path = state.get("current_scene_path")
    if scene_path:
        try:
            scene_data = ws.read_json(scene_path)
            location = scene_data.get("physical_location", "")
            if location:
                safe_name = location.replace("/", "_").replace("\\", "_")
                location_design_path = (
                    f"03_lore_bible/designs/locations/{safe_name}.png"
                )
                if not ws.exists(location_design_path):
                    print(
                        f"🎨 [Production Designer] Location design missing for '{location}' — generating..."
                    )
                    novel_text = state.get("novel_text", "")
                    extraction_prompt = f"""Extract a PURELY VISUAL description of the location '{location}' from the provided novel text.
                    Include: architectural style, interior/exterior details, lighting conditions, color palette, atmosphere, and any distinctive features.
                    STRICT RULE: Output ONLY the visual description text. No markdown headers, no conversational filler.
                    
                    Novel Text:
                    {novel_text[:50000]}
                    """
                    t0 = time.time()
                    desc_resp = agent.llm.generate_text(
                        extraction_prompt, system_prompt=PRODUCTION_DESIGNER_PROMPT
                    )
                    elapsed = time.time() - t0
                    clean_desc = (
                        desc_resp.text.replace("#", "").replace("**", "").strip()
                    )
                    print(
                        f"🎨 [Production Designer] Location '{location}' description extracted in {elapsed:.1f}s: {clean_desc[:200]}..."
                    )
                    try:
                        agent.generate_location_design(
                            location, clean_desc[:500], master_style
                        )
                    except Exception as e:
                        print(
                            f"🎨 [Production Designer] ⚠️  Failed to generate location design for '{location}': {e}"
                        )
                else:
                    print(
                        f"🎨 [Production Designer] Location design already exists for '{location}' — skipping"
                    )
        except Exception as e:
            print(f"🎨 [Production Designer] ⚠️  Could not read scene for location: {e}")

    # 3. Generate entity designs for current shot
    if plan:
        novel_text = state.get("novel_text", "")
        for entity in plan.active_entities:
            design_path = f"03_lore_bible/designs/{entity}.png"
            if not ws.exists(design_path):
                print(
                    f"🎨 [Production Designer] Design missing for '{entity}' — generating..."
                )
                extraction_prompt = f"""Extract a PURELY VISUAL physical description for the entity '{entity}' from the provided novel text.
                Include: facial features, clothing, body type, and age.
                STRICT RULE: Output ONLY the visual description text. No markdown headers, no conversational filler, no 'As an art director...', no introductory or concluding remarks.
                
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
                    f"🎨 [Production Designer] Entity '{entity}' description extracted in {elapsed:.1f}s: {clean_desc[:200]}..."
                )
                try:
                    agent.generate_design(entity, clean_desc[:500], master_style)
                except Exception as e:
                    print(
                        f"🎨 [Production Designer] ⚠️  Failed to generate design for '{entity}': {e}"
                    )
                    print(
                        f"🎨 [Production Designer] Continuing without design for '{entity}'"
                    )
            else:
                print(
                    f"🎨 [Production Designer] Design already exists for '{entity}' — skipping"
                )

    print(f"🎨 [Production Designer] === NODE EXIT ===")
    return {}
