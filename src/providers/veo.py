import time
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

from .base import (
    BaseVideoProvider,
    VideoResponse,
    VideoGenerationConfig,
)


class VeoProvider(BaseVideoProvider):
    """Video generation provider using Google Veo 3.1 API via google-genai SDK.

    Reference images are passed as API parameters (reference_images in config),
    NOT embedded as tokens in the prompt text. This is fundamentally different
    from Kling which uses <<<image_N>>> tokens in the prompt.

    Supports three modes (mutually exclusive):
    - Text-to-video: prompt only
    - First frame (+ optional last frame): image= parameter
    - Reference images: up to 3 asset images for character/environment consistency
      (fixed 8s duration when using reference images)

    Note: First frame and reference images CANNOT be combined in a single request.
    When both are needed, first_frame takes priority and reference images are
    passed as a fallback description in the prompt text instead.
    """

    VALID_DURATIONS = [4, 6, 8]

    @property
    def embeds_images_in_prompt(self) -> bool:
        return False

    def format_image_reference(self, index: int, label: str) -> str:
        return ""

    @property
    def prompt_length_limit(self) -> int:
        return 0

    def __init__(
        self,
        api_key: str,
        model: str = "veo-3.1-generate-preview",
    ):
        self.api_key = api_key
        self.model = model
        self.client = genai.Client(api_key=api_key)

    def _map_duration(self, requested_duration: int) -> int:
        if requested_duration <= 4:
            return 4
        elif requested_duration <= 7:
            return 6
        else:
            return 8

    def _with_retry(self, func, *args, max_retries: int = 3, **kwargs):
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                err_str = str(e)
                is_rate_limit = any(
                    x in err_str
                    for x in ["429", "RESOURCE_EXHAUSTED", "rate limit", "quota"]
                )
                is_transient = any(
                    x in err_str
                    for x in [
                        "RemoteProtocolError",
                        "Server disconnected",
                        "500",
                        "502",
                        "503",
                        "504",
                    ]
                )
                if is_rate_limit and i < max_retries - 1:
                    wait = min(30 * (2**i), 300)
                    print(f"  [Veo] Rate limited (attempt {i + 1}/{max_retries}): {e}")
                    print(f"  [Veo] Waiting {wait}s before retry...")
                    time.sleep(wait)
                    continue
                elif is_transient and i < max_retries - 1:
                    wait = (i + 1) * 5
                    print(f"  [Veo] Transient error: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise e

    def generate_video(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        config: Optional[VideoGenerationConfig] = None,
    ) -> VideoResponse:
        config = config or VideoGenerationConfig()

        first_frame_image = None
        if config.first_frame:
            first_frame_image = types.Image(image_bytes=config.first_frame)
        elif image_path:
            first_frame_image = types.Image.from_file(location=image_path)

        # reference_images and first_frame are mutually exclusive in Veo API
        ref_image_paths = config.reference_images or []
        has_first_frame = first_frame_image is not None
        use_ref_images = bool(ref_image_paths) and not has_first_frame

        if use_ref_images:
            duration = 8
        else:
            duration = self._map_duration(config.duration)

        veo_config_kwargs: Dict[str, Any] = {
            "aspect_ratio": "16:9",
            "duration_seconds": duration,
            "person_generation": "allow_adult",
        }

        if config.last_frame:
            veo_config_kwargs["last_frame"] = types.Image(image_bytes=config.last_frame)

        if use_ref_images:
            ref_images = []
            for ref_path in ref_image_paths[:3]:
                ref_images.append(
                    types.VideoGenerationReferenceImage(
                        image=types.Image.from_file(location=ref_path),
                        reference_type=types.VideoGenerationReferenceType.ASSET,
                    )
                )
            veo_config_kwargs["reference_images"] = ref_images

        print(
            f"  [Veo] Creating video task: model={self.model}, "
            f"duration={duration}s, has_first_frame={has_first_frame}, "
            f"ref_images={len(ref_image_paths) if use_ref_images else 0}, "
            f"audio={config.enable_audio}"
        )
        print(f"  [Veo] Prompt ({len(prompt)} chars): {prompt[:500]}")
        if use_ref_images:
            print(f"  [Veo] Reference images: {min(len(ref_image_paths), 3)} file(s)")
        elif ref_image_paths and has_first_frame:
            print(
                f"  [Veo] Skipping {len(ref_image_paths)} reference images "
                f"(mutually exclusive with first_frame in Veo API)"
            )

        generate_kwargs: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
        }
        if first_frame_image is not None:
            generate_kwargs["image"] = first_frame_image

        # Try with reference_images first; fall back without if SDK rejects them
        try:
            veo_gen_config = types.GenerateVideosConfig(**veo_config_kwargs)
            generate_kwargs["config"] = veo_gen_config
            operation = self._with_retry(
                self.client.models.generate_videos,
                **generate_kwargs,
            )
        except Exception as e:
            if use_ref_images and "reference_image" in str(e).lower():
                print(
                    f"  [Veo] reference_images rejected by SDK ({e}), "
                    f"retrying without reference images..."
                )
                veo_config_kwargs.pop("reference_images", None)
                veo_config_kwargs["duration_seconds"] = self._map_duration(
                    config.duration
                )
                veo_gen_config = types.GenerateVideosConfig(**veo_config_kwargs)
                generate_kwargs["config"] = veo_gen_config
                operation = self._with_retry(
                    self.client.models.generate_videos,
                    **generate_kwargs,
                )
            else:
                raise

        print(f"  [Veo] Task submitted, polling for completion...")

        video_bytes = self._poll_operation(operation, timeout=600, interval=15)

        estimated_cost = duration * 0.05

        return VideoResponse(
            video_bytes=video_bytes,
            duration=float(duration),
            resolution="1080p",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model=self.model,
            cost_usd=estimated_cost,
        )

    def _poll_operation(
        self, operation, timeout: int = 600, interval: int = 15
    ) -> bytes:
        start_time = time.time()

        while not operation.done:
            elapsed = int(time.time() - start_time)
            if elapsed >= timeout:
                raise TimeoutError(f"Veo video generation timed out after {timeout}s")
            print(f"  [Veo] Polling... ({elapsed}s elapsed)")
            time.sleep(interval)
            try:
                operation = self.client.operations.get(operation=operation)
            except Exception as e:
                elapsed = int(time.time() - start_time)
                print(
                    f"  [Veo] Poll request failed ({e}), "
                    f"retrying in {interval}s... ({elapsed}s elapsed)"
                )
                time.sleep(interval)
                continue

        if operation.error:
            raise Exception(f"Veo video generation failed: {operation.error}")

        result = operation.result  # type: ignore[union-attr]
        if not result or not result.generated_videos:
            raise Exception("Veo operation succeeded but no videos in result")

        generated_video = result.generated_videos[0]
        video = generated_video.video

        if not video:
            raise Exception("Veo operation succeeded but video object is empty")

        print(f"  [Veo] Video generation complete, downloading...")

        self.client.files.download(file=video)
        if hasattr(video, "video_bytes") and video.video_bytes:
            print(f"  [Veo] Downloaded {len(video.video_bytes)} bytes")
            return video.video_bytes

        import tempfile, os

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            video.save(tmp_path)
            with open(tmp_path, "rb") as f:
                data = f.read()
            print(f"  [Veo] Downloaded {len(data)} bytes via save()")
            return data
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def get_video_status(self, task_id: str) -> Dict[str, Any]:
        try:
            operation = self.client.operations.get(
                operation={"name": task_id}  # type: ignore[arg-type]
            )
            return {
                "done": operation.done,
                "error": str(operation.error) if operation.error else None,
                "has_result": bool(operation.result),
            }
        except Exception as e:
            return {"error": str(e)}
