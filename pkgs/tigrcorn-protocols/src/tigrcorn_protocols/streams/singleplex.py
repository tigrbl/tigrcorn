from .base import LogicalStream


class SingleplexStream(LogicalStream):
    def __init__(self, stream_id: int = 1) -> None:
        super().__init__(stream_id=stream_id, multiplexed=False)
