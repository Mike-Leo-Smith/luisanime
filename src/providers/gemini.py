import json
import base64
import time
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
    def __init__(
        self,
        api_key: str,
        model: str,
        image_model: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.image_model = image_model or "gemini-3.1-flash-image-preview"
        # Using v1alpha for experimental multimodal features
        self.client = genai.Client(
            api_key=api_key, http_options={"api_version": "v1alpha"}
        )

    def _upload_media(self, media_path: str) -> Any:
        path = Path(media_path)
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
        
        return file

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        config = config or GenerationConfig()
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
            ),
        )
        return LLMResponse(
            text=response.text or "",
            usage={},
            model=self.model,
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
            contents.append(file)
        
        contents.append(prompt)

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                temperature=config.temperature,
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text or "{}")

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
                contents.append(file)
        
        contents.append(prompt)

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                temperature=config.temperature,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        return json.loads(response.text or "{}")

    def generate_image(
        self, 
        prompt: str, 
        config: Optional[ImageGenerationConfig] = None,
        reference_media: Optional[Union[str, List[str]]] = None
    ) -> ImageResponse:
        """
        Multimodal image generation. 
        Supports providing reference images/video in the content stream.
        """
        contents = []
        if reference_media:
            paths = [reference_media] if isinstance(reference_media, str) else reference_media
            for p in paths:
                file = self._upload_media(p)
                contents.append(file)
        
        contents.append(prompt)

        print(f"  [GeminiProvider] Generating image with {self.image_model}...")
        response = self.client.models.generate_content(
            model=self.image_model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
            ),
        )
        
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    return ImageResponse(
                        image_bytes=part.inline_data.data,
                        mime_type=part.inline_data.mime_type,
                        usage={},
                        model=self.image_model,
                    )
        raise ValueError(f"No image part found in {self.image_model} response")

    def analyze_image(
        self, image_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        file = self._upload_media(image_path)
        response = self.client.models.generate_content(
            model=self.model,
            contents=[file, prompt],
        )
        return LLMResponse(text=response.text or "", usage={}, model=self.model)

    def analyze_video(self, video_path: str, prompt: str, config: Optional[GenerationConfig] = None) -> LLMResponse:
        return self.analyze_image(video_path, prompt, config)

    def edit_image(
        self,
        image_path: str,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
    ) -> ImageResponse:
        raise NotImplementedError("Image editing not yet implemented for GeminiProvider")
