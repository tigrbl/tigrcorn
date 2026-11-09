from __future__ import annotations

from .imports import *
from .helpers import *
from .ports import _normalize_sockaddr
from .impairment import UDPImpairmentPolicy

class _PacketTraceWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._handle = path.open('w', encoding='utf-8')

    def write(self, *, direction: str, transport: str, local: tuple[str, int], remote: tuple[str, int], payload: bytes) -> None:
        record = {
            'timestamp': time.time(),
            'direction': direction,
            'transport': transport,
            'local': {'host': local[0], 'port': local[1]},
            'remote': {'host': remote[0], 'port': remote[1]},
            'length': len(payload),
            'payload_hex': payload.hex(),
        }
        with self._lock:
            self._handle.write(json.dumps(record, sort_keys=True) + '\n')
            self._handle.flush()

    def close(self) -> None:
        try:
            self._handle.close()
        except Exception:
            pass


class _TCPRelay(threading.Thread):
    def __init__(self, source: socket.socket, sink: socket.socket, writer: _PacketTraceWriter, *, direction: str, local: tuple[str, int], remote: tuple[str, int]) -> None:
        super().__init__(daemon=True)
        self.source = source
        self.sink = sink
        self.writer = writer
        self.direction = direction
        self.local = local
        self.remote = remote

    def run(self) -> None:
        try:
            while True:
                chunk = self.source.recv(65535)
                if not chunk:
                    break
                self.writer.write(direction=self.direction, transport='tcp', local=self.local, remote=self.remote, payload=chunk)
                self.sink.sendall(chunk)
        except OSError:
            pass
        finally:
            try:
                self.sink.shutdown(socket.SHUT_WR)
            except OSError:
                pass


class TCPRecordProxy:
    def __init__(self, *, listen_host: str, listen_port: int, target_host: str, target_port: int, packet_trace_path: Path, ip_family: str = 'ipv4') -> None:
        family = socket.AF_INET6 if ip_family == 'ipv6' else socket.AF_INET
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self._server = socket.socket(family, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if family == socket.AF_INET6:
            self._server.bind((listen_host, listen_port, 0, 0))
        else:
            self._server.bind((listen_host, listen_port))
        self._server.listen(5)
        self._server.settimeout(0.2)
        self._writer = _PacketTraceWriter(packet_trace_path)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._connections: list[tuple[socket.socket, socket.socket]] = []

    def start(self) -> None:
        self._thread.start()

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                client_sock, _client_addr = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                server_sock = socket.create_connection((self.target_host, self.target_port), timeout=5.0)
            except OSError:
                client_sock.close()
                continue
            self._connections.append((client_sock, server_sock))
            local_client = _normalize_sockaddr(client_sock.getsockname())
            remote_server = _normalize_sockaddr(server_sock.getpeername())
            local_server = _normalize_sockaddr(server_sock.getsockname())
            remote_client = _normalize_sockaddr(client_sock.getpeername())
            c2s = _TCPRelay(client_sock, server_sock, self._writer, direction='client_to_server', local=local_client, remote=remote_server)
            s2c = _TCPRelay(server_sock, client_sock, self._writer, direction='server_to_client', local=local_server, remote=remote_client)
            c2s.start()
            s2c.start()

    def close(self) -> None:
        self._stop.set()
        try:
            self._server.close()
        except OSError:
            pass
        self._thread.join(timeout=1.0)
        for left, right in self._connections:
            try:
                left.close()
            except OSError:
                pass
            try:
                right.close()
            except OSError:
                pass
        self._writer.close()


class UDPRecordProxy:
    def __init__(self, *, listen_host: str, listen_port: int, target_host: str, target_port: int, packet_trace_path: Path, ip_family: str = 'ipv4', impairment: UDPImpairmentPolicy | None = None) -> None:
        family = socket.AF_INET6 if ip_family == 'ipv6' else socket.AF_INET
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self._downstream = socket.socket(family, socket.SOCK_DGRAM)
        self._upstream = socket.socket(family, socket.SOCK_DGRAM)
        if family == socket.AF_INET6:
            self._downstream.bind((listen_host, listen_port, 0, 0))
            self._upstream.bind((listen_host, 0, 0, 0))
        else:
            self._downstream.bind((listen_host, listen_port))
            self._upstream.bind((listen_host, 0))
        self._downstream.setblocking(False)
        self._upstream.setblocking(False)
        self._writer = _PacketTraceWriter(packet_trace_path)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._last_client: tuple[str, int] | None = None
        self._impairment = impairment

    def _forward_payloads(self, direction: str, payload: bytes) -> tuple[bytes, ...]:
        if self._impairment is None:
            return (payload,)
        if self._impairment.profile.delay_seconds:
            time.sleep(self._impairment.profile.delay_seconds)
        return self._impairment.apply(direction, payload)

    def start(self) -> None:
        self._thread.start()

    def _loop(self) -> None:
        selector = selectors.DefaultSelector()
        selector.register(self._downstream, selectors.EVENT_READ)
        selector.register(self._upstream, selectors.EVENT_READ)
        target = (self.target_host, self.target_port)
        try:
            while not self._stop.is_set():
                events = selector.select(timeout=0.2)
                for key, _mask in events:
                    if key.fileobj is self._downstream:
                        try:
                            payload, addr = self._downstream.recvfrom(65535)
                        except OSError:
                            continue
                        self._last_client = _normalize_sockaddr(addr)
                        self._writer.write(
                            direction='client_to_server',
                            transport='udp',
                            local=_normalize_sockaddr(self._downstream.getsockname()),
                            remote=(self.target_host, self.target_port),
                            payload=payload,
                        )
                        for forwarded in self._forward_payloads('client_to_server', payload):
                            try:
                                self._upstream.sendto(forwarded, target)
                            except OSError:
                                continue
                    elif key.fileobj is self._upstream:
                        try:
                            payload, _addr = self._upstream.recvfrom(65535)
                        except OSError:
                            continue
                        if self._last_client is None:
                            continue
                        self._writer.write(
                            direction='server_to_client',
                            transport='udp',
                            local=_normalize_sockaddr(self._upstream.getsockname()),
                            remote=self._last_client,
                            payload=payload,
                        )
                        for forwarded in self._forward_payloads('server_to_client', payload):
                            try:
                                self._downstream.sendto(forwarded, self._last_client)
                            except OSError:
                                continue
        finally:
            selector.close()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        try:
            self._downstream.close()
        except OSError:
            pass
        try:
            self._upstream.close()
        except OSError:
            pass
        self._writer.close()

__all__ = [name for name in globals() if not name.startswith('__')]
