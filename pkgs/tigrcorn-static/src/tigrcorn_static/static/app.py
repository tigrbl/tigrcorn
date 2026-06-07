from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from .representations import StaticRepresentationMixin
from .responses import StaticResponseMixin


class StaticFilesApp(StaticResponseMixin, StaticRepresentationMixin):
    def __init__(
        self,
        directory: str | Path,
        *,
        index_file: str | None = "index.html",
        dir_to_file: bool = True,
        expires: int | None = None,
        default_headers: Iterable[tuple[bytes, bytes] | tuple[str, str]] = (),
        apply_content_coding: bool = True,
        content_coding_policy: str = "allowlist",
        content_codings: Iterable[str] = ("br", "gzip", "deflate"),
        use_precompressed_sidecars: bool = True,
        precompressed_codings: Iterable[str] = ("br", "gzip"),
    ) -> None:
        self.directory = Path(directory).resolve()
        self.index_file = index_file
        self.dir_to_file = bool(dir_to_file)
        self.expires = None if expires is None else int(expires)
        self.default_headers = [
            (
                name if isinstance(name, bytes) else str(name).encode("latin1"),
                value if isinstance(value, bytes) else str(value).encode("latin1"),
            )
            for name, value in default_headers
        ]
        self.apply_content_coding = apply_content_coding
        self.content_coding_policy = str(content_coding_policy)
        self.content_codings = tuple(str(coding) for coding in content_codings)
        self.use_precompressed_sidecars = bool(use_precompressed_sidecars)
        self.precompressed_codings = tuple(str(coding).lower() for coding in precompressed_codings)
        self._etag_cache: dict[tuple[str, int, int], bytes] = {}

    @staticmethod
    def _supports_file_response(scope: dict) -> bool:
        extensions = scope.get("extensions") or {}
        return bool(extensions.get("tigrcorn.http.response.file"))

    @staticmethod
    def _supports_pathsend(scope: dict) -> bool:
        extensions = scope.get("extensions") or {}
        return "http.response.pathsend" in extensions

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            raise RuntimeError("StaticFilesApp only supports HTTP scopes")
        method = str(scope.get("method", "GET")).upper()
        if method not in {"GET", "HEAD"}:
            await send(
                {
                    "type": "http.response.start",
                    "status": 405,
                    "headers": [(b"allow", b"GET, HEAD"), (b"content-type", b"text/plain; charset=utf-8")],
                }
            )
            await send({"type": "http.response.body", "body": b"method not allowed"})
            return
        request_headers = [(bytes(name).lower(), bytes(value)) for name, value in scope.get("headers", [])]
        supports_file_response = self._supports_file_response(scope)
        supports_pathsend = self._supports_pathsend(scope)
        response = await self._response_for_path(
            method,
            scope.get("path", "/"),
            request_headers,
            supports_streaming_response=supports_file_response or supports_pathsend,
        )
        await send({"type": "http.response.start", "status": response.status, "headers": response.headers})
        if response.preprocessed:
            pathsend_segment = self._pathsend_segment(response) if supports_pathsend else None
            if pathsend_segment is not None:
                await send({"type": "http.response.pathsend", "path": os.fspath(pathsend_segment.path)})
                return
            if supports_file_response and response.segments:
                await send(
                    {
                        "type": "tigrcorn.http.response.file",
                        "segments": self._serialize_segments(response.segments),
                        "more_body": False,
                    }
                )
                return
        await send({"type": "http.response.body", "body": response.body})
