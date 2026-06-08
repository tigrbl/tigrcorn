from __future__ import annotations

from pathlib import Path

_PARTS = ['source_00.part', 'source_01.part', 'source_02.part', 'source_03.part']
_VIRTUAL_FILE = Path(__file__).resolve().parents[4] / 'tools/create_release_assembly_checkpoint.py'
_source = ''.join((Path(__file__).with_name(name).read_text(encoding='utf-8') for name in _PARTS))
globals()['__file__'] = str(_VIRTUAL_FILE)
exec(compile(_source, str(_VIRTUAL_FILE), 'exec'), globals())
