from dubber.application.ports.translator import TranslatorProvider
from dubber.application.dto.config import TranslatorConfig
from dubber.infrastructure.translator.openrouter import OpenRouterTranslatorProvider


class TranslatorFactory:
    _registry: dict[str, type[TranslatorProvider]] = {
        "openrouter": OpenRouterTranslatorProvider,
    }

    @classmethod
    def create(cls, config: TranslatorConfig) -> TranslatorProvider:
        provider_cls = cls._registry.get(config.provider)
        if not provider_cls:
            raise ValueError(f"Unknown translator provider: {config.provider}")
        return provider_cls(config)

    @classmethod
    def register(
        cls, name: str, provider_cls: type[TranslatorProvider]
    ) -> None:
        cls._registry[name] = provider_cls
