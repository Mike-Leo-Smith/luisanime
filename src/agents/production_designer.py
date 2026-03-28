from typing import Dict, Any, List, Optional
from src.agents.base import BaseCreative
from src.pipeline.state import AFCState
from src.providers.base import ImageGenerationConfig
from src.agents.prompts import PRODUCTION_DESIGNER_PROMPT

class ProductionDesignerAgent(BaseCreative):
    def generate_master_style(self, novel_context: str) -> str:
        """Generates a comprehensive master style description including historical era."""
        print("🎨 [Production Designer] Generating master style description and identifying era...")
        
        style_key = self.project_config.get("video", {}).get("style", "cinematic")
        preset = self.project_config.get("style_presets", {}).get(style_key, {})
        
        prompt = f"""Analyze the provided novel excerpt and determine its historical era/setting. 
Then, create a PURELY VISUAL cinematic style guide that blends this historical period with the theme: '{style_key}'.

User Style Preset: {preset.get('prompt_prefix', '')} {preset.get('prompt_suffix', '')}

Include:
1. IDENTIFIED ERA: (e.g. 19th Century France, Futuristic Cyberpunk, Ancient China)
2. VISUAL STYLE: Lighting, color palette, camera lens characteristics, and texture.
3. PERIOD DETAILS: Specific architectural or fashion cues to maintain historical/setting fidelity.

STRICT RULE: Output ONLY the descriptive guide. No conversational filler.
Keep it under 1000 characters.

Novel Excerpt:
{novel_context[:20000]}
"""

        response = self.llm.generate_text(prompt, system_prompt=PRODUCTION_DESIGNER_PROMPT)
        style_desc = response.text.replace("#", "").replace("**", "").strip()
        
        self.workspace.write_file("03_lore_bible/master_style.md", style_desc)
        print(f"🎨 [Production Designer] Master style bible established with era-specific guidance.")
        return style_desc

    def generate_design(self, entity_name: str, description: str, master_style: str) -> str:
        """Generates a locked visual reference image for an entity obeying master style."""
        print(f"🎨 [Production Designer] Lazily creating visual design for: {entity_name}...")
        
        style_key = self.project_config.get("video", {}).get("style", "cinematic")
        preset = self.project_config.get("style_presets", {}).get(style_key, {})
        prefix = preset.get("prompt_prefix", "")
        suffix = preset.get("prompt_suffix", "")

        # Focus prompt on the SUBJECT, use style as a modifier.
        prompt = f"{prefix} A high-quality concept art character/environment design sheet. Subject: {entity_name}. Description: {description}. Style: {suffix}. Consistent artistic look following these guidelines: {master_style[:300]}. White background, clear details, single focus."
        
        if len(prompt) > 1400:
            prompt = prompt[:1400]
            
        config = ImageGenerationConfig()
        image_path = f"03_lore_bible/designs/{entity_name}.png"
        
        # Log prompt next to image
        self.log_prompt("ProductionDesigner", f"DESIGN_{entity_name}", prompt, custom_path=f"{image_path}.prompt.txt")
        
        response = self.image_gen.generate_image(prompt=prompt, config=config)
        
        self.workspace.save_media(image_path, response.image_bytes)
        print(f"🎨 [Production Designer] Design saved: {image_path}")
        return image_path

def production_designer_node(state: AFCState) -> Dict:
    from src.pipeline.workspace import AgenticWorkspace
    ws = AgenticWorkspace(state["workspace_root"])
    agent = ProductionDesignerAgent.from_config(ws, state["project_config"])
    
    # 1. Ensure Master Style exists
    try:
        master_style = ws.read_file("03_lore_bible/master_style.md")
    except:
        novel_text = state.get("novel_text", "")
        master_style = agent.generate_master_style(novel_text)
    
    # 2. Check for lazy design generation based on current shot entities
    plan = state.get("active_shot_plan")
    if plan:
        novel_text = state.get("novel_text", "")
        for entity in plan.active_entities:
            design_path = f"03_lore_bible/designs/{entity}.png"
            if not ws.exists(design_path):
                # Lazy generate
                extraction_prompt = f"""Extract a PURELY VISUAL physical description for the entity '{entity}' from the provided novel text.
                Include: facial features, clothing, body type, and age.
                STRICT RULE: Output ONLY the visual description text. No markdown headers, no conversational filler, no 'As an art director...', no introductory or concluding remarks.
                
                Novel Text:
                {novel_text[:50000]}
                """
                desc_resp = agent.llm.generate_text(extraction_prompt, system_prompt=PRODUCTION_DESIGNER_PROMPT)
                
                # Clean up any potential markdown or roleplay leftover
                clean_desc = desc_resp.text.replace("#", "").replace("**", "").strip()
                if "Visual Description:" in clean_desc:
                    clean_desc = clean_desc.split("Visual Description:")[1].strip()
                
                agent.generate_design(entity, clean_desc[:500], master_style)
                
    return {}
