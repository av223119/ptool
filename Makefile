VENV := venv

dev: venv
	$(VENV)/bin/pip install --editable .[dev]
	
venv: pyproject.toml
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip

