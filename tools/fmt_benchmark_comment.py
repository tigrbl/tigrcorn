#!/usr/bin/env python3
"""Format a bounded benchmark summary from a pull request workflow."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MAX_SUMMARY_BYTES = 128_000
PROFILE_ID = re.compile(r'[A-Za-z0-9_-]{1,80}')


def format_comment(summary: object, run_url: str) -> str:
    if not isinstance(summary, dict):
        raise ValueError('expected a benchmark summary object')
    profiles = summary.get('profiles')
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= 100:
        raise ValueError('expected 1 to 100 benchmark profiles')
    results: dict[str, bool] = {}
    compared = 0
    for profile in profiles:
        if not isinstance(profile, dict):
            raise ValueError('expected a benchmark profile object')
        name = profile.get('profile_id')
        passed = profile.get('passed')
        if not isinstance(name, str) or not PROFILE_ID.fullmatch(name) or name in results:
            raise ValueError('invalid or repeated benchmark profile ID')
        if type(passed) is not bool:
            raise ValueError('invalid benchmark profile verdict')
        baseline_evaluated = profile.get('baseline_evaluated', False)
        if type(baseline_evaluated) is not bool:
            raise ValueError('invalid benchmark baseline verdict')
        compared += baseline_evaluated
        results[name] = passed

    passed_count = sum(results.values())
    lines = [
        '<!-- benchmark-results -->',
        '## Benchmark measurements',
        '',
        f'{passed_count}/{len(results)} profiles passed their configured checks.',
        (
            f'{compared}/{len(results)} profiles were also compared with the reference baseline.'
            if compared else 'This run used absolute thresholds without a reference baseline comparison.'
        ),
        f'[Workflow run and full measurement artifacts]({run_url})',
    ]
    failed_profiles = [name for name, passed in results.items() if not passed]
    if failed_profiles:
        lines.extend(['', 'Profiles that failed their checks:'])
        lines.extend(f'- `{name}`' for name in failed_profiles)
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary', type=Path)
    parser.add_argument('run_url')
    args = parser.parse_args()
    if args.summary.is_symlink() or not args.summary.is_file():
        parser.error('expected a regular benchmark summary file')
    with args.summary.open('rb') as stream:
        data = stream.read(MAX_SUMMARY_BYTES + 1)
    if len(data) > MAX_SUMMARY_BYTES:
        parser.error('benchmark summary exceeds size limit')
    try:
        print(format_comment(json.loads(data), args.run_url))
    except ValueError as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
