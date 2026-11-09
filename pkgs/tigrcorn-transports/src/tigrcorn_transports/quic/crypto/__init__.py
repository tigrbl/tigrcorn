from __future__ import annotations

from .aes import aes_encrypt_block
from .gcm import aes_gcm_decrypt, aes_gcm_encrypt
from .keys import (
    QUIC_V1_INITIAL_SALT,
    RETRY_INTEGRITY_KEY,
    RETRY_INTEGRITY_NONCE,
    QuicPacketProtectionKeys,
    derive_initial_packet_protection_keys,
    derive_initial_secret,
    derive_quic_packet_protection_keys,
    derive_secret,
    hkdf_expand,
    hkdf_expand_label,
    hkdf_extract,
    packet_nonce,
    update_quic_secret,
)
from .packets import (
    aes_header_protection_mask,
    apply_header_protection,
    build_retry_pseudo_packet,
    compute_retry_integrity_tag,
    encode_packet_number,
    generate_connection_id,
    make_integrity_tag,
    protect_payload,
    protect_quic_packet,
    reconstruct_packet_number,
    remove_header_protection,
    unprotect_payload,
    unprotect_quic_packet,
    verify_integrity_tag,
    verify_retry_integrity_tag,
)
