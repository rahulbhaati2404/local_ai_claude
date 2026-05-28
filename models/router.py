from core.config import settings


class ModelRouter:
    def route_generation_model(
        self,
        prompt_length: int
    ) -> str:

        if prompt_length < 10:
            return settings.OLLAMA_LIGHT_MODEL

        return settings.OLLAMA_DEFAULT_MODEL

    def route_embedding_model(self) -> str:
        return settings.HF_EMBEDDING_MODEL


model_router = ModelRouter()