import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from google import genai
from google.genai import types
from .base import (
    BaseLLMProvider,
    BaseImageProvider,
    LLMResponse,
    ImageResponse,
    GenerationConfig,
    ImageGenerationConfig,
)


class GeminiProvider(BaseLLMProvider, BaseImageProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        image_model: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.image_model = image_model or "imagen-4.0-generate-001"
        self.client = genai.Client(
            api_key=api_key, http_options={"api_version": "v1alpha"}
        )

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        config = config or GenerationConfig()

        contents = prompt
        if system_prompt:
            contents = f"{system_prompt}\n\n{prompt}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
                top_p=config.top_p,
            ),
        )

        text = response.text or ""
        prompt_tokens = (
            int(response.usage_metadata.prompt_token_count)
            if response.usage_metadata
            and response.usage_metadata.prompt_token_count is not None
            else 0
        )
        completion_tokens = (
            int(response.usage_metadata.candidates_token_count)
            if response.usage_metadata
            and response.usage_metadata.candidates_token_count is not None
            else 0
        )
        return LLMResponse(
            text=text,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            model=self.model,
            finish_reason=str(response.candidates[0].finish_reason)
            if response.candidates
            else None,
        )

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> Dict[str, Any]:
        config = config or GenerationConfig()
        config.temperature = 0.1

        json_prompt = f"{prompt}\n\nRespond with valid JSON only."
        response = self.generate_text(json_prompt, system_prompt, config)

        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())

    def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> Dict[str, Any]:
        config = config or GenerationConfig()

        contents = prompt
        if system_prompt:
            contents = f"{system_prompt}\n\n{prompt}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
                top_p=config.top_p,
                response_schema=response_schema,
            ),
        )

        text = response.text or "{}"
        return json.loads(text)

    def analyze_image(
        self, image_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        config = config or GenerationConfig()

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")

        response = self.client.models.generate_content(
            model=self.model,
            contents=[prompt, image_part],
            config=types.GenerateContentConfig(
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
            ),
        )

        text = response.text or ""
        prompt_tokens = 0
        completion_tokens = 0
        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count or 0
            completion_tokens = response.usage_metadata.candidates_token_count or 0
        return LLMResponse(
            text=text,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            model=self.model,
        )

    def generate_image(
        self, prompt: str, config: Optional[ImageGenerationConfig] = None
    ) -> ImageResponse:
        config = config or ImageGenerationConfig()

        response = self.client.models.generate_images(
            model=self.image_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=config.num_images,
            ),
        )

        if not response.generated_images or len(response.generated_images) == 0:
            raise ValueError("No image data returned")
        img = response.generated_images[0].image
        if img is None or img.image_bytes is None:
            raise ValueError("No image data returned")

        return ImageResponse(
            image_bytes=img.image_bytes,
            mime_type="image/png",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model=self.image_model,
        )

    def edit_image(
        self,
        image_path: str,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
    ) -> ImageResponse:
        raise NotImplementedError("Image editing not implemented for Gemini")
