from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config_from_namespace


class AppInterfaceDetectionPrecedenceTests(unittest.TestCase):
    def test_cli_over_env_over_config_file_for_app_interface(self) -> None:
        parser = build_parser()
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmp:
            path = Path(tmp) / "tigrcorn.json"
            path.write_text(json.dumps({"app": {"target": "tests.fixtures_pkg.appmod:app", "interface": "asgi3"}}), encoding="utf-8")
            ns = parser.parse_args(["--config", str(path), "--app-interface", "tigr-asgi-contract"])

            with patch.dict(os.environ, {"TIGRCORN_APP_INTERFACE": "asgi3"}, clear=False):
                config = build_config_from_namespace(ns)

        self.assertEqual(config.app.interface, "tigr-asgi-contract")

    def test_env_over_config_file_for_app_interface(self) -> None:
        parser = build_parser()
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmp:
            path = Path(tmp) / "tigrcorn.json"
            path.write_text(json.dumps({"app": {"target": "tests.fixtures_pkg.appmod:app", "interface": "asgi3"}}), encoding="utf-8")
            ns = parser.parse_args(["--config", str(path)])

            with patch.dict(os.environ, {"TIGRCORN_APP_INTERFACE": "tigr-asgi-contract"}, clear=False):
                config = build_config_from_namespace(ns)

        self.assertEqual(config.app.interface, "tigr-asgi-contract")

    def test_env_file_over_config_file_but_below_process_env(self) -> None:
        parser = build_parser()
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmp:
            config_path = Path(tmp) / "tigrcorn.json"
            env_path = Path(tmp) / ".env"
            config_path.write_text(json.dumps({"app": {"interface": "asgi3", "env_file": str(env_path)}}), encoding="utf-8")
            env_path.write_text("TIGRCORN_APP_INTERFACE=tigr-asgi-contract\n", encoding="utf-8")
            ns = parser.parse_args(["--config", str(config_path)])

            config = build_config_from_namespace(ns)

            with patch.dict(os.environ, {"TIGRCORN_APP_INTERFACE": "asgi3"}, clear=False):
                env_config = build_config_from_namespace(ns)

        self.assertEqual(config.app.interface, "tigr-asgi-contract")
        self.assertEqual(env_config.app.interface, "asgi3")
