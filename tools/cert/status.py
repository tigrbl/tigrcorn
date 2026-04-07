from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.compat.release_gates import evaluate_promotion_target, evaluate_release_gates


def main() -> int:
    root = Path(".")
    authoritative = evaluate_release_gates(root)
    strict = evaluate_release_gates(root, boundary_path="docs/review/conformance/certification_boundary.strict_target.json")
    promotion = evaluate_promotion_target(root)
    payload = {
        "authoritative_release_gates": {"passed": authoritative.passed, "failures": authoritative.failures},
        "strict_release_gates": {"passed": strict.passed, "failures": strict.failures},
        "promotion_target": {"passed": promotion.passed},
    }
    print(json.dumps(payload, indent=2))
    return 0 if authoritative.passed and strict.passed and promotion.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
