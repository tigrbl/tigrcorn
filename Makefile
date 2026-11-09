.PHONY: test certification-env-freeze release_certification-release-workflow

test:
	PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -v


certification-env-freeze:
	PYTHONPATH=src python tools/freeze_certification_environment.py


release_certification-release-workflow:
	PYTHONPATH=src python tools/run_release_certification_release_workflow.py
