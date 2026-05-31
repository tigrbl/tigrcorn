from __future__ import annotations

import unittest

from tigrcorn.contract import (
    alt_svc_contract_map,
    asgi3_compat_scope,
    asgi_extension_bridge,
    compatibility_feature_parity,
    content_coding_contract_map,
    early_hints_contract_map,
    observability_contract_metadata,
    proxy_normalization_contract_map,
    static_delivery_contract_map,
    trailers_contract_map,
    unit_identity,
)
from tigrcorn.errors import ProtocolError


class CompatHTTPBoundaryTests(unittest.TestCase):
    def test_asgi3_compat_layer_preserves_scope_and_declares_adapter(self) -> None:
        scope = asgi3_compat_scope({"type": "http", "method": "GET", "path": "/items"})

        self.assertEqual(scope["type"], "http")
        self.assertEqual(scope["extensions"]["tigrcorn.compat"]["interface"], "asgi3")
        self.assertFalse(scope["extensions"]["tigrcorn.compat"]["native_contract"])

    def test_asgi_extension_bridge_exports_unit_capabilities_and_http_maps(self) -> None:
        unit = unit_identity("unit-1", family="request", binding="http")
        feature_map = alt_svc_contract_map('h3=":443"', max_age=60)
        bridge = asgi_extension_bridge(
            unit=unit,
            capabilities={"request": ["http"]},
            feature_maps=[feature_map],
        )

        self.assertEqual(bridge["tigrcorn.unit"]["unit_id"], "unit-1")
        self.assertEqual(bridge["tigrcorn.capabilities"], {"request": ["http"]})
        self.assertEqual(bridge["tigrcorn.http_features"][0]["feature"], "alt-svc")

    def test_compat_feature_parity_matrix_rows_are_feature_scoped(self) -> None:
        row = compatibility_feature_parity(
            "feat:contract-http-event-map",
            native_contract=True,
            asgi3_compat=True,
            notes="event map parity",
        )

        self.assertEqual(row.as_dict()["feature_id"], "feat:contract-http-event-map")
        self.assertTrue(row.as_dict()["native_contract"])
        with self.assertRaises(ProtocolError):
            compatibility_feature_parity("contract-http-event-map", native_contract=True, asgi3_compat=True)

    def test_alt_svc_contract_map_targets_response_start_metadata(self) -> None:
        mapping = alt_svc_contract_map('h3=":443"', max_age=86400, persist=True)

        self.assertEqual(mapping.feature, "alt-svc")
        self.assertEqual(mapping.contract_events, ("http.response.start",))
        self.assertEqual(mapping.metadata["max_age"], 86400)

    def test_content_coding_contract_map_targets_headers_and_body(self) -> None:
        mapping = content_coding_contract_map(("gzip", "br"))

        self.assertEqual(mapping.feature, "content-coding")
        self.assertIn("http.response.start", mapping.contract_events)
        self.assertIn("http.response.body", mapping.contract_events)
        self.assertEqual(mapping.metadata["codings"], ["gzip", "br"])

    def test_early_hints_contract_map_declares_103_response_start(self) -> None:
        mapping = early_hints_contract_map([(b"link", b"</style.css>; rel=preload")])

        self.assertEqual(mapping.feature, "early-hints")
        self.assertEqual(mapping.metadata["status"], 103)
        self.assertEqual(mapping.contract_events, ("http.response.start",))

    def test_proxy_normalization_contract_map_targets_request_metadata(self) -> None:
        mapping = proxy_normalization_contract_map(trusted=True, forwarded_for="203.0.113.10", scheme="https")

        self.assertEqual(mapping.feature, "proxy-normalization")
        self.assertEqual(mapping.contract_events, ("http.request",))
        self.assertEqual(mapping.metadata["scheme"], "https")

    def test_static_delivery_contract_map_targets_pathsend_and_body(self) -> None:
        mapping = static_delivery_contract_map("/assets/app.css", range_request=True, etag='"abc"')

        self.assertEqual(mapping.feature, "static-delivery")
        self.assertIn("http.response.pathsend", mapping.contract_events)
        self.assertIn("http.response.pathsend", mapping.asgi_extensions)
        self.assertTrue(mapping.metadata["range_request"])
        with self.assertRaises(ProtocolError):
            static_delivery_contract_map("relative/path")

    def test_trailers_contract_map_targets_request_and_response_trailers(self) -> None:
        mapping = trailers_contract_map(request=True, response=True)

        self.assertEqual(mapping.feature, "trailers")
        self.assertIn("http.request.trailers", mapping.contract_events)
        self.assertIn("http.response.trailers", mapping.contract_events)
        self.assertIn("tigrcorn.http.request_trailers", mapping.asgi_extensions)

    def test_observability_contract_metadata_is_boundary_feature_and_unit_scoped(self) -> None:
        metadata = observability_contract_metadata(
            unit_id="unit-1",
            feature_id="feat:observability-contract-metadata",
            boundary_id="bnd:compat-http-next",
            attributes={"carrier": "http3"},
        )

        payload = metadata["tigrcorn.observability"]
        self.assertEqual(payload["unit_id"], "unit-1")
        self.assertEqual(payload["boundary_id"], "bnd:compat-http-next")
        self.assertEqual(payload["attributes"]["carrier"], "http3")
        with self.assertRaises(ProtocolError):
            observability_contract_metadata(unit_id="", feature_id="feat:x", boundary_id="bnd:y")


if __name__ == "__main__":
    unittest.main()
