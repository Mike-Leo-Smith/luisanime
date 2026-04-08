from typing import Dict, Any, Optional
import os
from .base import BaseLLMProvider, BaseImageProvider, BaseVideoProvider
from .gemini import GeminiProvider
from .minimax import MiniMaxProvider
from .openai_compat import OpenAICompatibleProvider
from .kling import KlingProvider
from .veo import VeoProvider


class ProviderFactory:
    @classmethod
    def create_llm(cls, config: Dict[str, Any]) -> BaseLLMProvider:
        provider_type = config.get("provider", "gemini").lower()
        api_key = cls._resolve_api_key(config.get("api_key"))

        if provider_type == "gemini":
            return GeminiProvider(
                api_key=api_key,
                model=config.get("model", "gemini-3.1-pro"),
                image_model=config.get("image_model"),
            )
        elif provider_type == "openai":
            return OpenAICompatibleProvider(
                api_key=api_key,
                base_url=config.get("base_url", "https://api.openai.com/v1"),
                model=config.get("model", "gpt-4"),
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider_type}")

    @classmethod
    def create_image(cls, config: Dict[str, Any]) -> BaseImageProvider:
        provider_type = config.get("provider", "gemini").lower()
        api_key = cls._resolve_api_key(config.get("api_key"))

        if provider_type == "gemini":
            return GeminiProvider(
                api_key=api_key,
                model=config.get("model", "gemini-3.1-pro"),
                image_model=config.get("image_model", config.get("model")),
            )
        elif provider_type == "minimax":
            return MiniMaxProvider(
                api_key=api_key,
                base_url=config.get("base_url", "https://api.minimaxi.com/v1"),
                image_model=config.get("model", "image-01"),
            )
        else:
            raise ValueError(f"Unknown image provider: {provider_type}")

    @classmethod
    def create_video(cls, config: Dict[str, Any]) -> BaseVideoProvider:
        provider_type = config.get("provider", "minimax").lower()
        api_key = cls._resolve_api_key(config.get("api_key"))

        if provider_type == "minimax":
            return MiniMaxProvider(
                api_key=api_key,
                base_url=config.get("base_url", "https://api.minimaxi.com/v1"),
                video_model=config.get("model", "MiniMax-Hailuo-02"),
            )
        elif provider_type == "kling":
            raw_secret = config.get("secret_key")
            if not raw_secret:
                raise ValueError(
                    "Kling provider requires 'secret_key' in model config "
                    "(e.g. secret_key: 'ENV:KLING_SECRET_KEY')"
                )
            secret_key = cls._resolve_api_key(raw_secret)
            return KlingProvider(
                access_key=api_key,
                secret_key=secret_key,
                base_url=config.get("base_url", "https://api-beijing.klingai.com"),
                model=config.get("model", "kling-v3-omni"),
                mode=config.get("mode", "pro"),
            )
        elif provider_type == "veo":
            return VeoProvider(
                api_key=api_key,
                model=config.get("model", "veo-3.1-generate-preview"),
            )
        else:
            raise ValueError(f"Unknown video provider: {provider_type}")

    @classmethod
    def _resolve_api_key(cls, key_or_env: Optional[str]) -> str:
        if not key_or_env:
            raise ValueError("API key not configured for provider")
        if key_or_env.startswith("ENV:"):
            env_var = key_or_env[4:]
            api_key = os.getenv(env_var)
            if not api_key:
                raise ValueError(f"Environment variable {env_var} not set")
            return api_key
        return key_or_env
