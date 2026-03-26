import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from .base import (
    BaseImageProvider,
    BaseVideoProvider,
    ImageResponse,
    VideoResponse,
    ImageGenerationConfig,
    VideoGenerationConfig,
)


class MiniMaxProvider(BaseImageProvider, BaseVideoProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.minimaxi.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def generate_image(
        self, prompt: str, config: Optional[ImageGenerationConfig] = None
    ) -> ImageResponse:
        config = config or ImageGenerationConfig()

        url = f"{self.base_url}/image_generation"
        payload = {
            "model": "image-01",
            "prompt": prompt,
            "width": config.width,
            "height": config.height,
            "n": config.num_images,
        }

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        data = response.json()
        task_id = data.get("task_id")

        image_url = self._poll_image_task(task_id)

        img_response = requests.get(image_url)
        img_response.raise_for_status()

        return ImageResponse(
            image_bytes=img_response.content,
            mime_type="image/png",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model="minimax-image-01",
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
            "model": "MiniMax-Hailuo-02",
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
            model="minimax-hailuo-02",
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
