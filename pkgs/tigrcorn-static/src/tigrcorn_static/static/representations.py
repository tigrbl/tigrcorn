from __future__ import annotations

import hashlib
import mimetypes
import time
from email.utils import formatdate
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from tigrcorn_asgi.send import FileBodySegment, iter_response_body_segments
from tigrcorn_core.utils.headers import append_if_missing, get_header

from .models import (
    HeaderList,
    MAX_ETAG_CACHE_ENTRIES,
    PRECOMPRESSED_SIDECAR_SUFFIXES,
    SelectedRepresentation,
)


class StaticRepresentationMixin:
    def _resolve_candidate(self, path: str) -> Path | None:
        decoded = unquote(path or "/")
        if "\x00" in decoded:
            return None
        parts: list[str] = []
        for part in PurePosixPath(decoded).parts:
            if part in {"", "/", "."}:
                continue
            if part == "..":
                return None
            if "\\" in part:
                return None
            parts.append(part)
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

    def _preferred_precompressed_codings(
        self,
        request_headers: list[tuple[bytes, bytes]],
    ) -> list[str]:
        header_value = get_header(request_headers, b"accept-encoding")
        if header_value is None:
            return []
        wildcard_q: float | None = None
        coding_q: dict[str, float] = {}
        order: dict[str, int] = {}
        for index, part in enumerate(header_value.decode("ascii", "ignore").split(",")):
            token = part.strip()
            if not token:
                continue
            name, *params = [piece.strip() for piece in token.split(";")]
            lower = name.lower()
            q = 1.0
            for param in params:
                if "=" not in param:
                    continue
                key, value = param.split("=", 1)
                if key.strip().lower() == "q":
                    q = self._parse_qvalue(value.strip())
            if lower == "*":
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

    def _select_representation(
        self,
        candidate: Path,
        request_headers: list[tuple[bytes, bytes]],
    ) -> SelectedRepresentation:
        origin_stat = candidate.stat()
        if not self.apply_content_coding or not self.use_precompressed_sidecars:
            return SelectedRepresentation(candidate, None, origin_stat.st_mtime, origin_stat.st_size, origin_stat.st_mtime_ns)
        if get_header(request_headers, b"range") is not None:
            return SelectedRepresentation(candidate, None, origin_stat.st_mtime, origin_stat.st_size, origin_stat.st_mtime_ns)
        for coding in self._preferred_precompressed_codings(request_headers):
            suffix = PRECOMPRESSED_SIDECAR_SUFFIXES.get(coding)
            if suffix is None:
                continue
            sidecar = candidate.with_name(candidate.name + suffix)
            if not sidecar.exists() or not sidecar.is_file():
                continue
            sidecar_stat = sidecar.stat()
            return SelectedRepresentation(
                sidecar,
                coding,
                max(origin_stat.st_mtime, sidecar_stat.st_mtime),
                sidecar_stat.st_size,
                max(origin_stat.st_mtime_ns, sidecar_stat.st_mtime_ns),
            )
        return SelectedRepresentation(candidate, None, origin_stat.st_mtime, origin_stat.st_size, origin_stat.st_mtime_ns)

    async def _representation_etag(self, representation: SelectedRepresentation) -> bytes:
        cache_key = (str(representation.path), representation.size, representation.mtime_ns)
        cached = self._etag_cache.get(cache_key)
        if cached is not None:
            return cached
        digest = hashlib.blake2s(digest_size=16)
        segment = FileBodySegment(str(representation.path), 0, representation.size)
        async for chunk in iter_response_body_segments((segment,)):
            digest.update(chunk)
        value = b'"' + digest.hexdigest().encode("ascii") + b'"'
        self._etag_cache[cache_key] = value
        if len(self._etag_cache) > MAX_ETAG_CACHE_ENTRIES:
            self._etag_cache.pop(next(iter(self._etag_cache)))
        return value

    def _base_headers(
        self,
        candidate: Path,
        representation: SelectedRepresentation,
        *,
        etag: bytes,
    ) -> HeaderList:
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        headers: HeaderList = [
            (b"content-type", content_type.encode("latin1")),
            (b"last-modified", formatdate(representation.mtime, usegmt=True).encode("ascii")),
            (b"etag", etag),
            *self.default_headers,
        ]
        if representation.content_encoding is not None:
            headers.append((b"content-encoding", representation.content_encoding.encode("ascii")))
            append_if_missing(headers, b"vary", b"accept-encoding")
        if self.expires is not None:
            if self.expires <= 0:
                headers.append((b"cache-control", b"no-store"))
            else:
                headers.append((b"cache-control", f"public, max-age={self.expires}".encode("ascii")))
                headers.append((b"expires", formatdate(time.time() + self.expires, usegmt=True).encode("ascii")))
        return headers
