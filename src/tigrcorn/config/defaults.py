from .model import ServerConfig
from .normalize import normalize_config


def default_config() -> ServerConfig:
    config = ServerConfig()
    normalize_config(config)
    return config
