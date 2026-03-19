from .model import ListenerConfig, ServerConfig


def default_config() -> ServerConfig:
    return ServerConfig(listeners=[ListenerConfig()])
