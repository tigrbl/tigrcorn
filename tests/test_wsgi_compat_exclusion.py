from __future__ import annotations

import unittest


@unittest.skip("placeholder: WSGI compatibility exclusion tests are planned in SSOT")
class WSGICompatExclusionTests(unittest.TestCase):
    def test_wsgi_compat_exclusion_contract(self) -> None:
        self.fail("placeholder")
