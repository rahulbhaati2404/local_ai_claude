from typing import Dict, Any

from core.logger import logger


class ModelRegistry:
    def __init__(self):
        self.models: Dict[str, Any] = {}

    def register(self, name: str, model: Any):
        logger.info(f"Registering model: {name}")
        self.models[name] = model

    def get(self, name: str):
        return self.models.get(name)

    def exists(self, name: str) -> bool:
        return name in self.models

    def list_models(self):
        return list(self.models.keys())


model_registry = ModelRegistry()