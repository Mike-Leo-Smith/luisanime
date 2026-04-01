from typing import Dict, Any, Optional
import os
from .base import BaseLLMProvider, BaseImageProvider, BaseVideoProvider
from .gemini import GeminiProvider
from .minimax import MiniMaxProvider
from .openai_compat import OpenAICompatibleProvider
from .kling import KlingProvider


class ProviderFactory:
    _llm_providers: Dict[str, Any] = {}
    _image_providers: Dict[str, Any] = {}
    _video_providers: Dict[str, Any] = {}

    @classmethod
    def register_llm(cls, name: str, provider_class):
        cls._llm_providers[name] = provider_class

    @classmethod
    def register_image(cls, name: str, provider_class):
        cls._image_providers[name] = provider_class

    @classmethod
    def register_video(cls, name: str, provider_class):
        cls._video_providers[name] = provider_class

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
            secret_key = cls._resolve_api_key(config.get("secret_key", ""))
            return KlingProvider(
                access_key=api_key,
                secret_key=secret_key,
                base_url=config.get("base_url", "https://api-beijing.klingai.com"),
                model=config.get("model", "kling-v3-omni"),
                mode=config.get("mode", "pro"),
            )
        else:
            raise ValueError(f"Unknown video provider: {provider_type}")

    @classmethod
    def _resolve_api_key(cls, key_or_env: str) -> str:
        if key_or_env.startswith("ENV:"):
            env_var = key_or_env[4:]
            api_key = os.getenv(env_var)
            if not api_key:
                raise ValueError(f"Environment variable {env_var} not set")
            return api_key
        return key_or_env


ProviderFactory.register_llm("gemini", GeminiProvider)
ProviderFactory.register_llm("openai", OpenAICompatibleProvider)
ProviderFactory.register_image("gemini", GeminiProvider)
ProviderFactory.register_image("minimax", MiniMaxProvider)
ProviderFactory.register_video("minimax", MiniMaxProvider)
ProviderFactory.register_video("kling", KlingProvider)
