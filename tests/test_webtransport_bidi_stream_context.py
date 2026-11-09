from __future__ import annotations

import unittest

from tests.support.webtransport_bidi_core_cases import WebTransportBidiCoreCases
from tests.support.webtransport_bidi_isolation_cases import WebTransportBidiIsolationCases
from tests.support.webtransport_bidi_regression_cases import WebTransportBidiRegressionCases


class WebTransportBidiStreamContextTests(
    WebTransportBidiCoreCases,
    WebTransportBidiIsolationCases,
    WebTransportBidiRegressionCases,
    unittest.IsolatedAsyncioTestCase,
):
    pass


if __name__ == "__main__":
    unittest.main()
