## Content

# Structured fields strict validation

This spec defines Tigrcorn's package-owned strict validation behavior for RFC 9651 structured fields.

## Scope

- `src/tigrcorn/http/structured_fields.py`
- `tests/test_structured_fields_validation.py`

## Required behavior

- The parser must reject malformed structured string escapes.
- The parser must reject control and non-ASCII characters inside structured strings.
- Structured keys must follow the RFC 9651 key grammar and reject uppercase characters.
- Structured tokens must keep RFC 9651-valid `:` and `/` characters when parsing and serializing.
- The serializer must reject invalid keys, invalid tokens, and invalid string values instead of emitting non-conformant wire output.

## Verification

- `tests/test_structured_fields_validation.py` covers malformed strings, invalid keys, valid escaped strings, valid `:` and `/` tokens, and serializer rejection paths.
- `tests/test_p8_sf.py` remains the broader RFC 9651 round-trip baseline for the structured-fields surface.
