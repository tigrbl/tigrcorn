from .base import LogicalStream


class MultiplexStream(LogicalStream):
    def __init__(self, stream_id: int) -> None:
        super().__init__(stream_id=stream_id, multiplexed=True)
