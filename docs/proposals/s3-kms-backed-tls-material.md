# Proposal Draft: S3-Backed and KMS-Backed TLS Material for Tigrcorn

Status: proposal draft

This draft is not an accepted ADR, SPEC, feature row, or release claim. It scopes possible native Tigrcorn support for loading or using S3-backed and KMS-backed key, certificate, and TLS-adjacent material. It does not propose turning Tigrcorn into object storage.

## Current Model

Tigrcorn currently models TLS material as local path configuration:

- `ssl_certfile`
- `ssl_keyfile`
- `ssl_keyfile_password`
- `ssl_ca_certs`
- `ssl_crl`

The TLS context builder reads these paths directly into bytes. There is no current first-class material provider interface for `s3://`, `kms://`, or other remote/provider-backed sources.

## Proposed Shape

Introduce a material resolution layer before TLS context construction.

```toml
[tls.cert]
uri = "s3://security-bucket/tigrcorn/tls/example.crt"
required_encryption = "AES256"

[tls.key]
uri = "s3://security-bucket/tigrcorn/tls/example.key"
required_encryption = "aws:kms"
kms_key_id = "alias/tigrcorn-tls-material"

[tls.ca_certs]
uri = "s3://security-bucket/tigrcorn/ca/clients.pem"
required_encryption = "aws:kms:dsse"
```

Core concepts:

- `MaterialSpec`: declarative source and policy for TLS-related material.
- `MaterialProviderBase`: resolves bytes from local files, S3 objects, environment variables, or other future sources.
- `MaterialMetadata`: captures source, observed encryption, version, ETag, last modified time, and provider diagnostics.
- `CryptoProviderBase`: optional separate surface for KMS operations that do not return private key material.

The first-class model should keep two concerns separate:

- S3-backed material loading: retrieve bytes for TLS inputs.
- KMS-backed crypto: use KMS for signing/decryption/key wrapping where supported.

## Good S3-Backed Candidates

These are good candidates because Tigrcorn already consumes them as startup/runtime material and can continue to treat them as bytes after provider resolution.

| Candidate | Why it fits | Suggested purpose |
|---|---|---|
| TLS server certificate PEM | Natural replacement for `ssl_certfile` | `tls_cert` |
| TLS private key PEM | Natural replacement for `ssl_keyfile` when operator accepts process-local key custody | `tls_key` |
| Encrypted TLS private key PEM | Works with existing `ssl_keyfile_password` concept | `tls_encrypted_key` |
| mTLS client CA bundle | Natural replacement for `ssl_ca_certs` | `client_ca_bundle` |
| CRL material | Natural replacement for `ssl_crl` | `crl` |
| OCSP staple or cache material | Fits revocation policy and TLS status workflows | `ocsp_material` |
| ALPN or TLS policy bundle | Allows governed TLS policy to be pulled from a controlled source | `tls_policy` |
| Deployment profile fragment | Fits Tigrcorn profile-driven operations | `deployment_profile` |
| QUIC retry or integrity secret blob | Can be loaded at startup if stored encrypted in S3 | `quic_secret` |

S3 provider policy should support requiring observed object encryption:

- `AES256` for SSE-S3.
- `aws:kms` for SSE-KMS.
- `aws:kms:dsse` or equivalent normalized value for DSSE-KMS, depending on SDK metadata shape.

For sensitive purposes such as private keys and QUIC secrets, missing or mismatched encryption metadata should fail closed.

## Good KMS-Backed Candidates

These are good candidates where Tigrcorn can use KMS to decrypt, unwrap, or eventually sign without treating KMS as file storage.

| Candidate | Why it fits | Suggested purpose |
|---|---|---|
| Decrypt encrypted TLS key blobs | KMS decrypts a ciphertext bundle into a process-local PEM | `tls_key_decrypt` |
| Decrypt QUIC retry/integrity secret | Keeps stored retry secret encrypted at rest | `quic_secret_decrypt` |
| Generate or unwrap local data keys | Useful for encrypted local caches or profile bundles | `data_key` |
| Sign TLS handshake messages | Theoretically keeps TLS private key in KMS, but only feasible if Tigrcorn TLS backend supports remote signing callbacks | `tls_remote_signing` |
| Sign release or configuration attestations | Useful for governed operator material, not protocol traffic | `attestation_signing` |

The practical first KMS slice should be decrypt/unwrap, not remote TLS signing. Remote TLS signing changes the TLS implementation boundary and would need dedicated protocol tests.

## Good DSSE-KMS Candidates

DSSE-KMS is an S3 server-side encryption mode for S3 objects. It is not a generic KMS operation mode. In Tigrcorn it should be modeled as a required S3 material policy.

Good DSSE-KMS candidates:

- TLS private key PEM stored in S3.
- Encrypted TLS private key PEM stored in S3.
- mTLS client CA bundle when trust material is considered sensitive by policy.
- CRL or OCSP material for regulated deployments.
- QUIC retry/integrity secret blobs stored in S3.
- Deployment profile fragments containing sensitive listener or topology details.
- Release/promotion evidence roots stored as S3 objects.

Poor DSSE-KMS candidates:

- Direct `kms://...` signing keys.
- Public TLS certificates where confidentiality is not meaningful.
- TLS session keys, QUIC traffic secrets, or other protocol-derived ephemeral state.
- HTTP response body encryption or application payload encryption.

## Non-Goals

- Do not make Tigrcorn an object-storage service.
- Do not add S3 static-origin delivery under this proposal.
- Do not imply DSSE-KMS applies to direct KMS signing operations.
- Do not replace TLS/QUIC protocol encryption with S3 or KMS semantics.
- Do not claim KMS-backed TLS private-key signing until the TLS backend can use remote signing callbacks.

## Proposal Interfaces

Sketch only:

```python
class MaterialProviderBase(Protocol):
    spec: MaterialSpec

    async def read_bytes(self) -> bytes: ...
    async def describe(self) -> MaterialMetadata: ...


class TLSMaterialBundle:
    certificate_pem: bytes
    private_key_pem: bytes
    private_key_password: bytes | None
    trusted_certificates: tuple[bytes, ...]
    crl_material: tuple[bytes, ...]
```

The existing config path fields could remain as shorthand for `file://` material specs.

```toml
[tls]
certfile = "s3://security-bucket/tigrcorn/tls/example.crt"
keyfile = "s3://security-bucket/tigrcorn/tls/example.key"
ca_certs = "s3://security-bucket/tigrcorn/ca/clients.pem"

[tls.material_policy]
require_encryption = true
private_key_required_encryption = "aws:kms:dsse"
```

## Open Questions

- Should URI support reuse existing `ssl_certfile` and `ssl_keyfile` fields, or introduce explicit `tls.cert.uri` and `tls.key.uri` fields?
- Should `s3://` private key loading require an explicit configuration acknowledgement?
- Should material be resolved once at startup, periodically refreshed, or reloaded only on operator signal?
- How should resolved material metadata appear in diagnostics without leaking sensitive paths or object names?
- Should KMS decrypt support precede or follow S3 material loading?
- Is remote TLS signing in scope for Tigrcorn, or should it remain out of bounds until the TLS backend has a stable signer abstraction?

## Suggested First Slice

1. Add a material resolver that treats existing local paths as `file://` material.
2. Add `s3://` material resolution for cert, key, CA bundle, CRL, and QUIC secret sources.
3. Add fail-closed S3 encryption-policy checks for sensitive material.
4. Add optional `kms://` decrypt support for encrypted key or secret blobs.
5. Keep direct KMS-backed TLS signing out of the initial slice.
6. Add SSOT ADR, SPEC, feature, claim, test, and evidence rows before treating this as accepted support.
