import os
import uuid
from typing import Any
from src.core.state import PipelineState
from src.config import load_config


def generate_image_keyframe(prompt: str, config: Any) -> str:
    print(f"--- IMAGE GEN: {prompt} ---")

    from google import genai
    from google.genai import types

    model_cfg = config.render_plane.storyboarder
    client = genai.Client(
        api_key=model_cfg.api_key, http_options={"api_version": "v1alpha"}
    )

    try:
        response = client.models.generate_images(
            model=model_cfg.model,
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1),
        )
        img = response.generated_images[0].image
        if img is None or img.image_bytes is None:
            raise ValueError("No image data returned")
        filename = f"keyframe_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join("./workspace", filename)
        os.makedirs("./workspace", exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(img.image_bytes)
        return filepath
    except Exception as e:
        print(f"Image generation failed: {e}")
        raise


def storyboarder(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- STORYBOARDER: Generating Keyframe for Shot {shot.id} ---")

    config = load_config()

    try:
        url = generate_image_keyframe(shot.prompt, config)
        state["shot_list"][idx].keyframe_url = url
        state["shot_list"][idx].status = "storyboarded"
    except Exception as e:
        print(f"Error in storyboarder: {e}")
        state["last_error"] = str(e)

    return state
