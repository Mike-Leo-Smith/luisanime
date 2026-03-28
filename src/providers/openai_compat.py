import json
from pathlib import Path
from typing import Optional, Dict, Any
import openai
from .base import (
    BaseLLMProvider,
    BaseImageProvider,
    LLMResponse,
    ImageResponse,
    GenerationConfig,
    ImageGenerationConfig,
)


class OpenAICompatibleProvider(BaseLLMProvider, BaseImageProvider):
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        config = config or GenerationConfig()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
        )

        text = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResponse(
            text=text,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            model=self.model,
            finish_reason=response.choices[0].finish_reason,
        )

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        media_path: Optional[str] = None,
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
        media_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        config = config or GenerationConfig()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def analyze_image(
        self, image_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        config = config or GenerationConfig()

        import base64

        with open(image_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode("utf-8")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        text = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResponse(
            text=text,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            model=self.model,
        )

    def analyze_video(
        self, video_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        raise NotImplementedError("Video analysis not supported by OpenAI provider yet")

    def generate_image(
        self, prompt: str, config: Optional[ImageGenerationConfig] = None
    ) -> ImageResponse:
        raise NotImplementedError(
            "Image generation not supported by generic OpenAI-compatible provider"
        )

    def edit_image(
        self,
        image_path: str,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
    ) -> ImageResponse:
        raise NotImplementedError("Image editing not supported")
