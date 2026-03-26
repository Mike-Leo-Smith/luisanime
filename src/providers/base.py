from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class GenerationConfig:
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95


@dataclass
class ImageGenerationConfig(GenerationConfig):
    width: int = 1024
    height: int = 1024
    num_images: int = 1


@dataclass
class VideoGenerationConfig(GenerationConfig):
    duration: int = 6
    fps: int = 24
    resolution: str = "1080p"


@dataclass
class LLMResponse:
    text: str
    usage: Dict[str, int]
    model: str
    finish_reason: Optional[str] = None


@dataclass
class ImageResponse:
    image_bytes: bytes
    mime_type: str
    usage: Dict[str, int]
    model: str


@dataclass
class VideoResponse:
    video_bytes: bytes
    duration: float
    resolution: str
    usage: Dict[str, int]
    model: str


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def analyze_image(
        self, image_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        pass


class BaseImageProvider(ABC):
    @abstractmethod
    def generate_image(
        self, prompt: str, config: Optional[ImageGenerationConfig] = None
    ) -> ImageResponse:
        pass

    @abstractmethod
    def edit_image(
        self,
        image_path: str,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
    ) -> ImageResponse:
        pass


class BaseVideoProvider(ABC):
    @abstractmethod
    def generate_video(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        config: Optional[VideoGenerationConfig] = None,
    ) -> VideoResponse:
        pass

    @abstractmethod
    def get_video_status(self, task_id: str) -> Dict[str, Any]:
        pass
