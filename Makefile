.PHONY: test

test:
	PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -v
