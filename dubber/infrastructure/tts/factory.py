from dubber.application.ports.tts import TTSProvider
from dubber.application.dto.config import TTSConfig
from dubber.infrastructure.tts.edge_tts import EdgeTTSProvider
from dubber.infrastructure.tts.openai_tts import OpenAITTSProvider


class TTSFactory:
    _registry: dict[str, type[TTSProvider]] = {
        "edge": EdgeTTSProvider,
        "openai": OpenAITTSProvider,
    }

    @classmethod
    def create(cls, config: TTSConfig) -> TTSProvider:
        if config.provider == "openai":
            raise ValueError("OpenAI TTS provider is not yet implemented")
        provider_cls = cls._registry.get(config.provider)
        if not provider_cls:
            raise ValueError(f"Unknown TTS provider: {config.provider}")
        return provider_cls(config)

    @classmethod
    def register(cls, name: str, provider_cls: type[TTSProvider]) -> None:
        cls._registry[name] = provider_cls
