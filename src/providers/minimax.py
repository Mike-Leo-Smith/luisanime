import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from .base import (
    BaseLLMProvider,
    BaseImageProvider,
    BaseVideoProvider,
    LLMResponse,
    ImageResponse,
    VideoResponse,
    GenerationConfig,
    ImageGenerationConfig,
    VideoGenerationConfig,
)


class MiniMaxProvider(BaseLLMProvider, BaseImageProvider, BaseVideoProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.minimaxi.com/v1",
        model: str = "MiniMax-Text-01",
        image_model: str = "image-01",
        video_model: str = "MiniMax-Hailuo-02",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.image_model = image_model
        self.video_model = video_model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        config = config or GenerationConfig()

        url = f"{self.base_url}/text/chatcompletion_v2"

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            text=content,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
            model=self.model,
            finish_reason=choice.get("finish_reason"),
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

        schema_prompt = f"""{prompt}

You must respond with a JSON object that follows this schema:
{json.dumps(response_schema, indent=2)}

Respond with valid JSON only."""

        return self.generate_json(schema_prompt, system_prompt, config)

    def analyze_image(
        self, image_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        raise NotImplementedError("Image analysis not supported by MiniMax")

    def generate_image(
        self, prompt: str, config: Optional[ImageGenerationConfig] = None
    ) -> ImageResponse:
        config = config or ImageGenerationConfig()

        url = f"{self.base_url}/image_generation"
        payload = {
            "model": self.image_model,
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "response_format": "url",
            "n": config.num_images,
        }

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        data = response.json()
        base_resp = data.get("base_resp", {})

        if base_resp.get("status_code") != 0:
            raise Exception(f"Image generation failed: {base_resp.get('status_msg')}")

        image_urls = data.get("data", {}).get("image_urls", [])
        if not image_urls:
            raise Exception("No image URLs in response")

        image_url = image_urls[0]
        img_response = requests.get(image_url)
        img_response.raise_for_status()

        return ImageResponse(
            image_bytes=img_response.content,
            mime_type="image/png",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model=self.image_model,
        )

    def _poll_image_task(self, task_id: str, timeout: int = 300) -> str:
        url = f"{self.base_url}/query/image_generation"
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = requests.get(f"{url}?task_id={task_id}", headers=self.headers)
            data = response.json()

            status = data.get("status")
            if status == "success":
                return data.get("file", {}).get("download_url")
            elif status == "fail":
                raise Exception(f"Image generation failed: {data.get('error_msg')}")

            time.sleep(2)

        raise TimeoutError(f"Image generation timed out after {timeout}s")

    def edit_image(
        self,
        image_path: str,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
    ) -> ImageResponse:
        raise NotImplementedError("Image editing not supported by MiniMax")

    def generate_video(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        config: Optional[VideoGenerationConfig] = None,
    ) -> VideoResponse:
        config = config or VideoGenerationConfig()

        url = f"{self.base_url}/video_generation"
        payload = {
            "model": self.video_model,
            "prompt": prompt,
            "duration": config.duration,
        }

        if image_path:
            with open(image_path, "rb") as f:
                import base64

                image_base64 = base64.b64encode(f.read()).decode("utf-8")
            payload["first_frame_image"] = f"data:image/png;base64,{image_base64}"

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        data = response.json()
        task_id = data.get("task_id")

        video_url = self._poll_video_task(task_id)

        video_response = requests.get(video_url)
        video_response.raise_for_status()

        return VideoResponse(
            video_bytes=video_response.content,
            duration=config.duration,
            resolution=config.resolution,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model=self.video_model,
        )

    def _poll_video_task(self, task_id: str, timeout: int = 600) -> str:
        url = f"{self.base_url}/query/video_generation"
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = requests.get(f"{url}?task_id={task_id}", headers=self.headers)
            data = response.json()

            status = data.get("status", "").lower()
            if status == "success":
                file_id = data.get("file_id")
                return self._get_download_url(file_id)
            elif status == "fail":
                raise Exception(f"Video generation failed: {data.get('error_msg')}")

            time.sleep(10)

        raise TimeoutError(f"Video generation timed out after {timeout}s")

    def _get_download_url(self, file_id: str) -> str:
        url = f"{self.base_url}/files/retrieve?file_id={file_id}"
        response = requests.get(url, headers=self.headers)
        data = response.json()
        return data.get("file", {}).get("download_url")

    def get_video_status(self, task_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/query/video_generation"
        response = requests.get(f"{url}?task_id={task_id}", headers=self.headers)
        return response.json()
