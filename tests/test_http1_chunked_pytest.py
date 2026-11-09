from tigrcorn.protocols.http1.serializer import finalize_chunked_body, serialize_http11_response_chunk


def test_chunk_serialization() -> None:
    assert serialize_http11_response_chunk(b"hello") == b"5\r\nhello\r\n"
    assert finalize_chunked_body() == b"0\r\n\r\n"
