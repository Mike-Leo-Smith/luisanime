import json
import base64
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
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
    COST_PER_MILLION_TOKENS = {
        "gemini-2.0-flash": 0.075,
        "gemini-2.0-pro": 1.25,
        "gemini-2.0-flash-image": 0.075,
    }

    def __init__(
        self,
        api_key: str,
        model: str,
        image_model: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.image_model = image_model or "gemini-2.0-flash-image"
        self.client = genai.Client(
            api_key=api_key, http_options={"api_version": "v1beta"}
        )
        self._upload_cache: Dict[str, Any] = {}

    def _estimate_cost(self, prompt: str, response_text: str = "") -> float:
        input_chars = len(prompt)
        output_chars = len(response_text)
        input_tokens = input_chars / 4
        output_tokens = output_chars / 4
        total_tokens = input_tokens + output_tokens
        cost_per_million = self.COST_PER_MILLION_TOKENS.get(self.model, 0.075)
        return (total_tokens / 1_000_000) * cost_per_million

    def _with_retry(self, func, *args, **kwargs):
        """Generic retry wrapper for Gemini API calls."""
        max_retries = 3
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                err_str = str(e)
                if any(
                    x in err_str
                    for x in [
                        "RemoteProtocolError",
                        "Server disconnected",
                        "500",
                        "502",
                        "503",
                        "504",
                    ]
                ):
                    if i < max_retries - 1:
                        wait = (i + 1) * 2
                        print(
                            f"  [GeminiProvider] Transient error: {e}. Retrying in {wait}s..."
                        )
                        time.sleep(wait)
                        continue
                raise e

    def _upload_media(self, media_path: str) -> Any:
        path = Path(media_path)

        # Calculate hash for cache key
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        # Check cache
        if file_hash in self._upload_cache:
            file = self._upload_cache[file_hash]
            try:
                # Verify file still exists on server
                file = self.client.files.get(name=file.name)
                if file.state.name == "ACTIVE":
                    print(
                        f"  [GeminiProvider] Using cached file: {file.name} for {path.name} (hash match)"
                    )
                    return file
            except:
                pass

        mime_type = "image/png"
        if path.suffix.lower() in [".mp4", ".mpeg", ".mov", ".avi"]:
            mime_type = "video/mp4"
        elif path.suffix.lower() in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"

        print(f"  [GeminiProvider] Uploading {path.name} ({mime_type})...")
        file = self.client.files.upload(file=str(path))

        # Robust polling for Video/Large images
        if mime_type.startswith("video") or path.stat().st_size > 10 * 1024 * 1024:
            print(f"  [GeminiProvider] Waiting for file {file.name} to be processed...")
            while file.state.name == "PROCESSING":
                time.sleep(2)
                file = self.client.files.get(name=file.name)

            if file.state.name == "FAILED":
                raise ValueError(f"File processing failed: {file.name}")
            print(f"  [GeminiProvider] File {file.name} is ACTIVE.")

        self._upload_cache[file_hash] = file
        return file

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        config = config or GenerationConfig()

        response = self._with_retry(
            self.client.models.generate_content,
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
            ),
        )
        cost = self._estimate_cost(prompt, response.text or "")
        return LLMResponse(
            text=response.text or "",
            usage={},
            model=self.model,
            cost_usd=cost,
        )

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        media_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        config = config or GenerationConfig()

        contents = []
        if media_path:
            file = self._upload_media(media_path)
            contents.append(
                types.Part.from_uri(file_uri=file.uri, mime_type=file.mime_type)
            )

        contents.append(types.Part.from_text(text=prompt))

        if media_path:
            gen_config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                temperature=config.temperature,
            )
        else:
            gen_config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                temperature=config.temperature,
                response_mime_type="application/json",
            )

        response = self._with_retry(
            self.client.models.generate_content,
            model=self.model,
            contents=contents,
            config=gen_config,
        )

        text = response.text or "{}"
        if media_path and not text.startswith("{"):
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

        return json.loads(text)

    def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        media_path: Optional[Union[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        config = config or GenerationConfig()

        contents = []
        if media_path:
            paths = [media_path] if isinstance(media_path, str) else media_path
            for p in paths:
                file = self._upload_media(p)
                contents.append(
                    types.Part.from_uri(file_uri=file.uri, mime_type=file.mime_type)
                )

        contents.append(types.Part.from_text(text=prompt))

        if media_path:
            gen_config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                temperature=config.temperature,
            )
        else:
            gen_config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                temperature=config.temperature,
                response_mime_type="application/json",
                response_schema=response_schema,
            )

        response = self._with_retry(
            self.client.models.generate_content,
            model=self.model,
            contents=contents,
            config=gen_config,
        )

        text = response.text or "{}"
        if media_path:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

        return json.loads(text)

    def generate_image(
        self,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
        reference_media: Optional[Union[str, List[str]]] = None,
    ) -> ImageResponse:
        contents = []
        if reference_media is None and config and config.reference_media:
            reference_media = config.reference_media

        if reference_media:
            paths = (
                [reference_media]
                if isinstance(reference_media, str)
                else reference_media
            )
            for p in paths:
                file = self._upload_media(p)
                contents.append(
                    types.Part.from_uri(file_uri=file.uri, mime_type=file.mime_type)
                )

        contents.append(types.Part.from_text(text=prompt))

        print(f"  [GeminiProvider] Generating image with {self.image_model}...")
        response = self._with_retry(
            self.client.models.generate_content,
            model=self.image_model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
            ),
        )

        image_cost = 0.02
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    return ImageResponse(
                        image_bytes=part.inline_data.data,
                        mime_type=part.inline_data.mime_type,
                        usage={},
                        model=self.image_model,
                        cost_usd=image_cost,
                    )
        raise ValueError(f"No image part found in {self.image_model} response")

    def analyze_image(
        self, image_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        file = self._upload_media(image_path)
        contents = [
            types.Part.from_uri(file_uri=file.uri, mime_type=file.mime_type),
            types.Part.from_text(text=prompt),
        ]

        response = self._with_retry(
            self.client.models.generate_content,
            model=self.model,
            contents=contents,
        )
        cost = self._estimate_cost(prompt, response.text or "")
        return LLMResponse(
            text=response.text or "", usage={}, model=self.model, cost_usd=cost
        )

    def analyze_video(
        self, video_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        return self.analyze_image(video_path, prompt, config)

    def edit_image(
        self,
        image_path: str,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
    ) -> ImageResponse:
        raise NotImplementedError(
            "Image editing not yet implemented for GeminiProvider"
        )
