import base64
import time
import jwt
import requests
from pathlib import Path
from typing import Optional, Dict, Any

from .base import (
    BaseVideoProvider,
    VideoResponse,
    VideoGenerationConfig,
)


class KlingProvider(BaseVideoProvider):
    """Video generation provider using Kling v3 Omni API.

    Requires two keys for JWT authentication:
    - access_key: Used as the JWT issuer (iss claim)
    - secret_key: Used to sign the JWT token (HS256)

    API docs: https://klingai.com/document-api/apiReference/model/OmniVideo
    """

    # Kling API status constants
    STATUS_SUBMITTED = "submitted"
    STATUS_PROCESSING = "processing"
    STATUS_SUCCEED = "succeed"
    STATUS_FAILED = "failed"

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        base_url: str = "https://api-beijing.klingai.com",
        model: str = "kling-v3-omni",
        mode: str = "pro",
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.mode = mode

    def _generate_jwt_token(self) -> str:
        """Generate a JWT token for Kling API authentication.

        Token is valid for 30 minutes (1800s) with 5s clock skew tolerance.
        """
        now = int(time.time())
        headers = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": self.access_key,
            "exp": now + 1800,
            "nbf": now - 5,
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256", headers=headers)

    def _get_auth_headers(self) -> Dict[str, str]:
        """Build request headers with fresh JWT token."""
        token = self._generate_jwt_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _resolution_to_aspect_ratio(self, resolution: str) -> str:
        """Map resolution string to Kling aspect ratio.

        Kling requires aspect_ratio when no first_frame image is provided.
        """
        resolution_map = {
            "1080p": "16:9",
            "720p": "16:9",
            "360p": "16:9",
            "portrait": "9:16",
            "square": "1:1",
        }
        return resolution_map.get(resolution, "16:9")

    def _encode_image_bytes(self, image_bytes: bytes) -> str:
        """Encode image bytes as pure base64 for the Kling API.

        Kling requires raw base64 without the data URI prefix.
        Sending 'data:image/...;base64,...' causes error 1201.
        """
        return base64.b64encode(image_bytes).decode("utf-8")

    def _encode_image_file(self, image_path: str) -> str:
        """Read and encode an image file to raw base64 (no data URI prefix)."""
        with open(image_path, "rb") as f:
            return self._encode_image_bytes(f.read())

    def generate_video(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        config: Optional[VideoGenerationConfig] = None,
    ) -> VideoResponse:
        """Generate a video using Kling v3 Omni API.

        Args:
            prompt: Text description for video generation.
            image_path: Optional path to a first-frame image file.
            config: Optional video generation configuration.

        Returns:
            VideoResponse with downloaded video bytes and metadata.
        """
        config = config or VideoGenerationConfig()

        url = f"{self.base_url}/v1/videos/omni-video"

        payload: Dict[str, Any] = {
            "model_name": self.model,
            "prompt": prompt,
            "duration": str(config.duration),
            "mode": self.mode,
            "sound": "on" if config.enable_audio else "off",
        }

        # Build image_list for first_frame and last_frame
        image_list = []

        if config.first_frame:
            image_list.append(
                {
                    "image_url": self._encode_image_bytes(config.first_frame),
                    "type": "first_frame",
                }
            )
        elif image_path:
            image_list.append(
                {
                    "image_url": self._encode_image_file(image_path),
                    "type": "first_frame",
                }
            )

        if config.last_frame:
            image_list.append(
                {
                    "image_url": self._encode_image_bytes(config.last_frame),
                    "type": "end_frame",
                }
            )

        if config.reference_images:
            for ref_path in config.reference_images:
                image_list.append(
                    {
                        "image_url": self._encode_image_file(ref_path),
                        "type": "reference",
                    }
                )

        if image_list:
            payload["image_list"] = image_list
        else:
            # Aspect ratio is required when no first_frame image is provided
            payload["aspect_ratio"] = self._resolution_to_aspect_ratio(
                config.resolution
            )

        # Control video reference (motion/camera transfer)
        if config.control_video_path:
            payload["video_list"] = [
                {
                    "video_url": config.control_video_path,
                    "refer_type": "feature",
                }
            ]

        print(
            f"  [Kling] Creating video task: model={self.model}, mode={self.mode}, duration={config.duration}s, sound={'on' if config.enable_audio else 'off'}"
        )
        print(f"  [Kling] Prompt: {prompt[:500]}")
        print(
            f"  [Kling] Image list: {len(image_list)} image(s) — types: {[img.get('type', 'reference') for img in image_list]}"
        )
        has_image_ref = "<<<image_" in prompt
        print(f"  [Kling] Prompt contains image reference tokens: {has_image_ref}")

        headers = self._get_auth_headers()
        response = requests.post(url, headers=headers, json=payload)
        if not response.ok:
            error_detail = ""
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text[:500]
            raise Exception(f"Kling API error {response.status_code}: {error_detail}")

        data = response.json()
        if data.get("code") != 0:
            raise Exception(
                f"Kling video creation failed: code={data.get('code')}, "
                f"message={data.get('message')}"
            )

        task_id = data["data"]["task_id"]
        print(f"  [Kling] Task created: {task_id}")

        # Poll until completion
        video_url, video_duration = self._poll_video_task(task_id)

        # Download the video (URLs expire in 30 days, download immediately)
        print(f"  [Kling] Downloading video from {video_url[:80]}...")
        video_response = requests.get(video_url)
        video_response.raise_for_status()

        # Use actual duration from API if available, otherwise config value
        actual_duration = (
            float(video_duration) if video_duration else float(config.duration)
        )

        # Kling pricing: roughly $0.14 per 5s in pro mode (estimate)
        estimated_cost = (actual_duration / 5.0) * 0.14

        return VideoResponse(
            video_bytes=video_response.content,
            duration=actual_duration,
            resolution=config.resolution,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model=self.model,
            cost_usd=estimated_cost,
        )

    def _poll_video_task(
        self, task_id: str, timeout: int = 600, interval: int = 10
    ) -> tuple:
        """Poll the Kling API until the video task completes.

        Args:
            task_id: The task ID from create request.
            timeout: Maximum seconds to wait (default 10 minutes).
            interval: Seconds between polls (default 10s).

        Returns:
            Tuple of (video_url, duration) from the completed task.

        Raises:
            Exception: If the task fails.
            TimeoutError: If polling exceeds the timeout.
        """
        url = f"{self.base_url}/v1/videos/omni-video/{task_id}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            headers = self._get_auth_headers()
            response = requests.get(url, headers=headers)
            if not response.ok:
                error_detail = ""
                try:
                    error_detail = response.json()
                except Exception:
                    error_detail = response.text[:500]
                raise Exception(
                    f"Kling poll API error {response.status_code}: {error_detail}"
                )

            data = response.json()
            if data.get("code") != 0:
                raise Exception(
                    f"Kling poll error: code={data.get('code')}, "
                    f"message={data.get('message')}"
                )

            task_data = data.get("data", {})
            status = task_data.get("task_status", "")

            if status == self.STATUS_SUCCEED:
                task_result = task_data.get("task_result", {})
                videos = task_result.get("videos", [])
                if not videos:
                    raise Exception("Kling task succeeded but no videos in result")

                video = videos[0]
                video_url = video.get("url")
                video_duration = video.get("duration")

                if not video_url:
                    raise Exception("Kling task succeeded but video URL is empty")

                print(f"  [Kling] Task {task_id} completed successfully")
                return video_url, video_duration

            elif status == self.STATUS_FAILED:
                error_msg = task_data.get("task_status_msg", "Unknown error")
                print(f"  [Kling] Task {task_id} failed: {error_msg}")
                raise Exception(f"Kling video generation failed: {error_msg}")

            else:
                elapsed = int(time.time() - start_time)
                print(f"  [Kling] Task {task_id} status: {status} ({elapsed}s elapsed)")

            time.sleep(interval)

        raise TimeoutError(
            f"Kling video generation timed out after {timeout}s for task {task_id}"
        )

    def get_video_status(self, task_id: str) -> Dict[str, Any]:
        """Get the current status of a video generation task.

        Args:
            task_id: The task ID to check.

        Returns:
            Raw API response as a dictionary.
        """
        url = f"{self.base_url}/v1/videos/omni-video/{task_id}"
        headers = self._get_auth_headers()
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
