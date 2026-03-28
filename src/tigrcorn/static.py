from __future__ import annotations

import hashlib
import mimetypes
import os
import time
from dataclasses import dataclass
from email.utils import formatdate
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import unquote

from tigrcorn.asgi.send import FileBodySegment, MemoryBodySegment, materialize_response_body_segments, iter_response_body_segments
from tigrcorn.http.conditional import apply_conditional_request
from tigrcorn.http.entity import apply_response_entity_semantics, finalize_response_content_length
from tigrcorn.http.range import ByteRange, FileRangePlan, plan_file_byte_ranges
from tigrcorn.protocols.http1.serializer import response_allows_body
from tigrcorn.types import ASGIApp
from tigrcorn.utils.headers import append_if_missing, get_header
from tigrcorn.utils.proxy import strip_root_path


HeaderList = list[tuple[bytes, bytes]]
_PRECOMPRESSED_SIDECAR_SUFFIXES: dict[str, str] = {'br': '.br', 'gzip': '.gz'}
_BUFFERED_DYNAMIC_CODING_MAX_BYTES = 256 * 1024
_MAX_ETAG_CACHE_ENTRIES = 1024


@dataclass(slots=True)
class StaticFileResponse:
    status: int
    headers: HeaderList
    body: bytes = b''
    segments: tuple[MemoryBodySegment | FileBodySegment, ...] = ()
    preprocessed: bool = False


@dataclass(slots=True)
class _SelectedRepresentation:
    path: Path
    content_encoding: str | None
    mtime: float
    size: int
    mtime_ns: int


class StaticFilesApp:
    def __init__(
        self,
        directory: str | Path,
        *,
        index_file: str | None = 'index.html',
        dir_to_file: bool = True,
        expires: int | None = None,
        default_headers: Iterable[tuple[bytes, bytes] | tuple[str, str]] = (),
        apply_content_coding: bool = True,
        content_coding_policy: str = 'allowlist',
        content_codings: Iterable[str] = ('br', 'gzip', 'deflate'),
        use_precompressed_sidecars: bool = True,
        precompressed_codings: Iterable[str] = ('br', 'gzip'),
    ) -> None:
        self.directory = Path(directory).resolve()
        self.index_file = index_file
        self.dir_to_file = bool(dir_to_file)
        self.expires = None if expires is None else int(expires)
        self.default_headers = [
            (
                name if isinstance(name, bytes) else str(name).encode('latin1'),
                value if isinstance(value, bytes) else str(value).encode('latin1'),
            )
            for name, value in default_headers
        ]
        self.apply_content_coding = apply_content_coding
        self.content_coding_policy = str(content_coding_policy)
        self.content_codings = tuple(str(coding) for coding in content_codings)
        self.use_precompressed_sidecars = bool(use_precompressed_sidecars)
        self.precompressed_codings = tuple(str(coding).lower() for coding in precompressed_codings)
        self._etag_cache: dict[tuple[str, int, int], bytes] = {}

    def _resolve_candidate(self, path: str) -> Path | None:
        decoded = unquote(path or '/')
        parts = [part for part in PurePosixPath(decoded).parts if part not in {'', '/', '.', '..'}]
        candidate = self.directory.joinpath(*parts).resolve()
        try:
            candidate.relative_to(self.directory)
        except ValueError:
            return None
        if candidate.is_dir():
            if not self.dir_to_file or not self.index_file:
                return None
            candidate = candidate / self.index_file
        try:
            candidate.relative_to(self.directory)
        except ValueError:
            return None
        return candidate

    @staticmethod
    def _parse_qvalue(raw: str) -> float:
        try:
            value = float(raw)
        except ValueError:
            return 0.0
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _preferred_precompressed_codings(self, request_headers: list[tuple[bytes, bytes]]) -> list[str]:
        header_value = get_header(request_headers, b'accept-encoding')
        if header_value is None:
            return []
        wildcard_q: float | None = None
        coding_q: dict[str, float] = {}
        order: dict[str, int] = {}
        for index, part in enumerate(header_value.decode('ascii', 'ignore').split(',')):
            token = part.strip()
            if not token:
                continue
            name, *params = [piece.strip() for piece in token.split(';')]
            lower = name.lower()
            q = 1.0
            for param in params:
                if '=' not in param:
                    continue
                key, value = param.split('=', 1)
                if key.strip().lower() == 'q':
                    q = self._parse_qvalue(value.strip())
            if lower == '*':
                wildcard_q = q
            else:
                coding_q[lower] = q
                order.setdefault(lower, index)

        ranked: list[tuple[float, int, str]] = []
        for index, coding in enumerate(self.precompressed_codings):
            q = coding_q.get(coding)
            if q is None:
                q = wildcard_q if wildcard_q is not None else 0.0
            if q <= 0.0:
                continue
            ranked.append((-q, order.get(coding, 1000 + index), coding))
        ranked.sort()
        return [coding for _neg_q, _order, coding in ranked]

    def _select_representation(self, candidate: Path, request_headers: list[tuple[bytes, bytes]]) -> _SelectedRepresentation:
        origin_stat = candidate.stat()
        if not self.apply_content_coding or not self.use_precompressed_sidecars:
            return _SelectedRepresentation(
                path=candidate,
                content_encoding=None,
                mtime=origin_stat.st_mtime,
                size=origin_stat.st_size,
                mtime_ns=origin_stat.st_mtime_ns,
            )
        if get_header(request_headers, b'range') is not None:
            return _SelectedRepresentation(
                path=candidate,
                content_encoding=None,
                mtime=origin_stat.st_mtime,
                size=origin_stat.st_size,
                mtime_ns=origin_stat.st_mtime_ns,
            )
        for coding in self._preferred_precompressed_codings(request_headers):
            suffix = _PRECOMPRESSED_SIDECAR_SUFFIXES.get(coding)
            if suffix is None:
                continue
            sidecar = candidate.with_name(candidate.name + suffix)
            if not sidecar.exists() or not sidecar.is_file():
                continue
            sidecar_stat = sidecar.stat()
            return _SelectedRepresentation(
                path=sidecar,
                content_encoding=coding,
                mtime=max(origin_stat.st_mtime, sidecar_stat.st_mtime),
                size=sidecar_stat.st_size,
                mtime_ns=max(origin_stat.st_mtime_ns, sidecar_stat.st_mtime_ns),
            )
        return _SelectedRepresentation(
            path=candidate,
            content_encoding=None,
            mtime=origin_stat.st_mtime,
            size=origin_stat.st_size,
            mtime_ns=origin_stat.st_mtime_ns,
        )

    async def _representation_etag(self, representation: _SelectedRepresentation) -> bytes:
        cache_key = (str(representation.path), representation.size, representation.mtime_ns)
        cached = self._etag_cache.get(cache_key)
        if cached is not None:
            return cached
        digest = hashlib.blake2s(digest_size=16)
        async for chunk in iter_response_body_segments((FileBodySegment(str(representation.path), 0, representation.size),)):
            digest.update(chunk)
        value = b'"' + digest.hexdigest().encode('ascii') + b'"'
        self._etag_cache[cache_key] = value
        if len(self._etag_cache) > _MAX_ETAG_CACHE_ENTRIES:
            self._etag_cache.pop(next(iter(self._etag_cache)))
        return value

    def _base_headers(self, candidate: Path, representation: _SelectedRepresentation, *, etag: bytes) -> HeaderList:
        content_type = mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream'
        headers: HeaderList = [
            (b'content-type', content_type.encode('latin1')),
            (b'last-modified', formatdate(representation.mtime, usegmt=True).encode('ascii')),
            (b'etag', etag),
            *self.default_headers,
        ]
        if representation.content_encoding is not None:
            headers.append((b'content-encoding', representation.content_encoding.encode('ascii')))
            append_if_missing(headers, b'vary', b'accept-encoding')
        if self.expires is not None:
            if self.expires <= 0:
                headers.append((b'cache-control', b'no-store'))
            else:
                headers.append((b'cache-control', f'public, max-age={self.expires}'.encode('ascii')))
                headers.append((b'expires', formatdate(time.time() + self.expires, usegmt=True).encode('ascii')))
        return headers

    async def _buffered_dynamic_coding_response(
        self,
        *,
        method: str,
        request_headers: list[tuple[bytes, bytes]],
        candidate: Path,
        representation: _SelectedRepresentation,
    ) -> StaticFileResponse:
        body = await materialize_response_body_segments((FileBodySegment(str(representation.path), 0, representation.size),))
        headers = self._base_headers(candidate, representation, etag=await self._representation_etag(representation))
        processed = apply_response_entity_semantics(
            method=method,
            request_headers=request_headers,
            response_headers=headers,
            body=body,
            status=200,
            apply_content_coding=True,
            content_coding_policy=self.content_coding_policy,
            supported_codings=self.content_codings,
            generate_etag=False,
        )
        segments = (MemoryBodySegment(processed.body),) if processed.body else ()
        return StaticFileResponse(
            status=processed.status,
            headers=processed.headers,
            body=processed.body,
            segments=segments,
            preprocessed=True,
        )

    @staticmethod
    def _multipart_segments(
        *,
        path: Path,
        plan: FileRangePlan,
        total_length: int,
        source_content_type: bytes | None,
    ) -> tuple[MemoryBodySegment | FileBodySegment, ...]:
        assert plan.boundary is not None
        segments: list[MemoryBodySegment | FileBodySegment] = []
        for item in plan.parts:
            lines = [b'--' + plan.boundary]
            if source_content_type is not None:
                lines.append(b'Content-Type: ' + source_content_type)
            lines.append(b'Content-Range: bytes ' + f'{item.start}-{item.end}/{total_length}'.encode('ascii'))
            segments.append(MemoryBodySegment(b'\r\n'.join(lines) + b'\r\n\r\n'))
            segments.append(FileBodySegment(str(path), item.start, item.end - item.start + 1))
            segments.append(MemoryBodySegment(b'\r\n'))
        segments.append(MemoryBodySegment(b'--' + plan.boundary + b'--\r\n'))
        return tuple(segments)

    async def _static_file_plan(
        self,
        *,
        method: str,
        request_headers: list[tuple[bytes, bytes]],
        candidate: Path,
        representation: _SelectedRepresentation,
        supports_file_response: bool,
    ) -> StaticFileResponse:
        etag = await self._representation_etag(representation)
        headers = self._base_headers(candidate, representation, etag=etag)
        conditional = apply_conditional_request(
            method=method.upper(),
            request_headers=request_headers,
            response_headers=headers,
            body=b'',
            status=200,
        )
        if conditional.not_modified or conditional.precondition_failed:
            processed = apply_response_entity_semantics(
                method=method,
                request_headers=request_headers,
                response_headers=conditional.headers,
                body=conditional.body,
                status=conditional.status,
                apply_content_coding=False,
                generate_etag=False,
            )
            segments = (MemoryBodySegment(processed.body),) if processed.body else ()
            return StaticFileResponse(
                status=processed.status,
                headers=processed.headers,
                body=processed.body,
                segments=segments,
                preprocessed=True,
            )

        plan = plan_file_byte_ranges(
            method=method,
            request_headers=request_headers,
            response_headers=conditional.headers,
            resource_length=representation.size,
            status=conditional.status,
        )
        headers = finalize_response_content_length(
            method=method.upper(),
            status=plan.status,
            headers=plan.headers,
            body_length=plan.body_length,
        )
        segments: tuple[MemoryBodySegment | FileBodySegment, ...]
        if method.upper() == 'HEAD' or not response_allows_body(plan.status) or plan.unsatisfied:
            segments = ()
        elif plan.applied and len(plan.parts) > 1:
            source_content_type = mimetypes.guess_type(str(candidate))[0]
            segments = self._multipart_segments(
                path=representation.path,
                plan=plan,
                total_length=representation.size,
                source_content_type=None if source_content_type is None else source_content_type.encode('latin1'),
            )
        elif plan.applied and len(plan.parts) == 1:
            item = plan.parts[0]
            segments = (FileBodySegment(str(representation.path), item.start, item.end - item.start + 1),)
        else:
            segments = (FileBodySegment(str(representation.path), 0, representation.size),)

        body = await materialize_response_body_segments(segments) if (segments and not supports_file_response) else b''
        return StaticFileResponse(
            status=plan.status,
            headers=headers,
            body=body,
            segments=segments,
            preprocessed=True,
        )

    async def _response_for_path(
        self,
        method: str,
        path: str,
        request_headers: list[tuple[bytes, bytes]],
        *,
        supports_streaming_response: bool,
    ) -> StaticFileResponse:
        candidate = self._resolve_candidate(path)
        if candidate is None or not candidate.exists() or not candidate.is_file():
            return StaticFileResponse(
                status=404,
                headers=[(b'content-type', b'text/plain; charset=utf-8')],
                body=b'not found',
            )
        representation = self._select_representation(candidate, request_headers)
        if (
            representation.content_encoding is None
            and self.apply_content_coding
            and get_header(request_headers, b'accept-encoding') is not None
            and get_header(request_headers, b'range') is None
            and representation.size <= _BUFFERED_DYNAMIC_CODING_MAX_BYTES
        ):
            return await self._buffered_dynamic_coding_response(
                method=method,
                request_headers=request_headers,
                candidate=candidate,
                representation=representation,
            )
        return await self._static_file_plan(
            method=method,
            request_headers=request_headers,
            candidate=candidate,
            representation=representation,
            supports_file_response=supports_streaming_response,
        )

    @staticmethod
    def _supports_file_response(scope: dict) -> bool:
        extensions = scope.get('extensions') or {}
        return bool(extensions.get('tigrcorn.http.response.file'))

    @staticmethod
    def _supports_pathsend(scope: dict) -> bool:
        extensions = scope.get('extensions') or {}
        return 'http.response.pathsend' in extensions

    @staticmethod
    def _pathsend_segment(response: StaticFileResponse) -> FileBodySegment | None:
        if not response.segments or len(response.segments) != 1:
            return None
        segment = response.segments[0]
        if not isinstance(segment, FileBodySegment):
            return None
        if segment.offset != 0:
            return None
        if segment.count is None:
            return segment
        try:
            size = Path(segment.path).stat().st_size
        except FileNotFoundError:
            return None
        return segment if segment.count == size else None

    @staticmethod
    def _serialize_segments(segments: tuple[MemoryBodySegment | FileBodySegment, ...]) -> list[dict]:
        serialized: list[dict] = []
        for segment in segments:
            if isinstance(segment, MemoryBodySegment):
                serialized.append({'type': 'memory', 'body': segment.data})
            else:
                serialized.append({'type': 'file', 'path': segment.path, 'offset': segment.offset, 'count': segment.count})
        return serialized

    async def __call__(self, scope, receive, send) -> None:
        if scope['type'] != 'http':
            raise RuntimeError('StaticFilesApp only supports HTTP scopes')
        method = str(scope.get('method', 'GET')).upper()
        if method not in {'GET', 'HEAD'}:
            await send(
                {
                    'type': 'http.response.start',
                    'status': 405,
                    'headers': [(b'allow', b'GET, HEAD'), (b'content-type', b'text/plain; charset=utf-8')],
                }
            )
            await send({'type': 'http.response.body', 'body': b'method not allowed'})
            return
        request_headers = [(bytes(name).lower(), bytes(value)) for name, value in scope.get('headers', [])]
        supports_file_response = self._supports_file_response(scope)
        supports_pathsend = self._supports_pathsend(scope)
        response = await self._response_for_path(
            method,
            scope.get('path', '/'),
            request_headers,
            supports_streaming_response=supports_file_response or supports_pathsend,
        )
        await send({'type': 'http.response.start', 'status': response.status, 'headers': response.headers})
        if response.preprocessed:
            pathsend_segment = self._pathsend_segment(response) if supports_pathsend else None
            if pathsend_segment is not None:
                await send({'type': 'http.response.pathsend', 'path': os.fspath(pathsend_segment.path)})
                return
            if supports_file_response and response.segments:
                await send(
                    {
                        'type': 'tigrcorn.http.response.file',
                        'segments': self._serialize_segments(response.segments),
                        'more_body': False,
                    }
                )
                return
        await send({'type': 'http.response.body', 'body': response.body})


async def _not_found_app(scope, receive, send) -> None:
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return
    if scope['type'] == 'websocket':
        await send({'type': 'websocket.close', 'code': 1000})
        return
    if scope['type'] != 'http':
        raise RuntimeError(f'unsupported scope type for static fallback: {scope["type"]!r}')
    if scope.get('method', 'GET').upper() not in {'GET', 'HEAD'}:
        await send({'type': 'http.response.start', 'status': 405, 'headers': [(b'allow', b'GET, HEAD'), (b'content-type', b'text/plain; charset=utf-8')]})
        await send({'type': 'http.response.body', 'body': b'method not allowed'})
        return
    await send({'type': 'http.response.start', 'status': 404, 'headers': [(b'content-type', b'text/plain; charset=utf-8')]})
    await send({'type': 'http.response.body', 'body': b'not found'})


def normalize_static_route(route: str | None) -> str:
    if not route:
        return '/'
    return ('/' + str(route).lstrip('/')).rstrip('/') or '/'


def _route_matches(route: str, path: str) -> bool:
    if route == '/':
        return True
    return path == route or path.startswith(route + '/')


def mount_static_app(
    app: ASGIApp | None,
    *,
    route: str,
    directory: str | Path,
    dir_to_file: bool = True,
    index_file: str | None = 'index.html',
    expires: int | None = None,
    apply_content_coding: bool = True,
    content_coding_policy: str = 'allowlist',
    content_codings: Iterable[str] = ('br', 'gzip', 'deflate'),
    use_precompressed_sidecars: bool = True,
    precompressed_codings: Iterable[str] = ('br', 'gzip'),
) -> ASGIApp:
    static_app = StaticFilesApp(
        directory,
        index_file=index_file,
        dir_to_file=dir_to_file,
        expires=expires,
        apply_content_coding=apply_content_coding,
        content_coding_policy=content_coding_policy,
        content_codings=content_codings,
        use_precompressed_sidecars=use_precompressed_sidecars,
        precompressed_codings=precompressed_codings,
    )
    fallback = app or _not_found_app
    normalized_route = normalize_static_route(route)

    async def wrapped(scope, receive, send) -> None:
        if scope['type'] != 'http':
            await fallback(scope, receive, send)
            return
        path = str(scope.get('path') or '/')
        if not _route_matches(normalized_route, path):
            await fallback(scope, receive, send)
            return
        raw_path = bytes(scope.get('raw_path') or path.encode('latin1'))
        mounted_path, mounted_raw_path = strip_root_path(path, raw_path, normalized_route)
        mounted_scope = dict(scope)
        mounted_scope['path'] = mounted_path
        mounted_scope['raw_path'] = mounted_raw_path
        if normalized_route != '/':
            existing_root = str(scope.get('root_path') or '')
            combined_root = (existing_root.rstrip('/') + normalized_route).rstrip('/') or '/'
            mounted_scope['root_path'] = combined_root
        await static_app(mounted_scope, receive, send)

    return wrapped


__all__ = ['StaticFilesApp', 'mount_static_app', 'normalize_static_route']
