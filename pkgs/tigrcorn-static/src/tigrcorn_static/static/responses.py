from __future__ import annotations

import mimetypes
from pathlib import Path

from tigrcorn_asgi.send import FileBodySegment, MemoryBodySegment, materialize_response_body_segments
from tigrcorn_core.utils.headers import get_header
from tigrcorn_http.conditional import apply_conditional_request
from tigrcorn_http.entity import apply_response_entity_semantics, finalize_response_content_length
from tigrcorn_http.range import FileRangePlan, plan_file_byte_ranges
from tigrcorn_protocols.http1.serializer import response_allows_body

from .models import BUFFERED_DYNAMIC_CODING_MAX_BYTES, StaticFileResponse


class StaticResponseMixin:
    async def _buffered_dynamic_coding_response(
        self,
        *,
        method: str,
        request_headers: list[tuple[bytes, bytes]],
        candidate: Path,
        representation,
    ) -> StaticFileResponse:
        segment = FileBodySegment(str(representation.path), 0, representation.size)
        body = await materialize_response_body_segments((segment,))
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
            lines = [b"--" + plan.boundary]
            if source_content_type is not None:
                lines.append(b"Content-Type: " + source_content_type)
            lines.append(b"Content-Range: bytes " + f"{item.start}-{item.end}/{total_length}".encode("ascii"))
            segments.append(MemoryBodySegment(b"\r\n".join(lines) + b"\r\n\r\n"))
            segments.append(FileBodySegment(str(path), item.start, item.end - item.start + 1))
            segments.append(MemoryBodySegment(b"\r\n"))
        segments.append(MemoryBodySegment(b"--" + plan.boundary + b"--\r\n"))
        return tuple(segments)

    async def _static_file_plan(
        self,
        *,
        method: str,
        request_headers: list[tuple[bytes, bytes]],
        candidate: Path,
        representation,
        supports_file_response: bool,
    ) -> StaticFileResponse:
        etag = await self._representation_etag(representation)
        headers = self._base_headers(candidate, representation, etag=etag)
        conditional = apply_conditional_request(
            method=method.upper(),
            request_headers=request_headers,
            response_headers=headers,
            body=b"",
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
            return StaticFileResponse(processed.status, processed.headers, processed.body, segments, True)

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
        if method.upper() == "HEAD" or not response_allows_body(plan.status) or plan.unsatisfied:
            segments = ()
        elif plan.applied and len(plan.parts) > 1:
            source_content_type = mimetypes.guess_type(str(candidate))[0]
            segments = self._multipart_segments(
                path=representation.path,
                plan=plan,
                total_length=representation.size,
                source_content_type=None if source_content_type is None else source_content_type.encode("latin1"),
            )
        elif plan.applied and len(plan.parts) == 1:
            item = plan.parts[0]
            segments = (FileBodySegment(str(representation.path), item.start, item.end - item.start + 1),)
        else:
            segments = (FileBodySegment(str(representation.path), 0, representation.size),)

        body = await materialize_response_body_segments(segments) if (segments and not supports_file_response) else b""
        return StaticFileResponse(plan.status, headers, body, segments, True)

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
            return StaticFileResponse(404, [(b"content-type", b"text/plain; charset=utf-8")], b"not found")
        representation = self._select_representation(candidate, request_headers)
        if (
            representation.content_encoding is None
            and self.apply_content_coding
            and get_header(request_headers, b"accept-encoding") is not None
            and get_header(request_headers, b"range") is None
            and representation.size <= BUFFERED_DYNAMIC_CODING_MAX_BYTES
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
    def _pathsend_segment(response: StaticFileResponse) -> FileBodySegment | None:
        if not response.segments or len(response.segments) != 1:
            return None
        segment = response.segments[0]
        if not isinstance(segment, FileBodySegment) or segment.offset != 0:
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
                serialized.append({"type": "memory", "body": segment.data})
            else:
                serialized.append({"type": "file", "path": segment.path, "offset": segment.offset, "count": segment.count})
        return serialized
