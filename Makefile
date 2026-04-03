.PHONY: test test-pytest certification-env-freeze phase9-release-workflow

test:
	PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -v

test-pytest:
	uv run python -m pytest tests/ -v


certification-env-freeze:
	PYTHONPATH=src python tools/freeze_certification_environment.py


phase9-release-workflow:
	PYTHONPATH=src python tools/run_phase9_release_workflow.py
