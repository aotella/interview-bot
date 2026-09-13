# Backend targets. Included from the root Makefile - run via `make
# backend-*` from the repo root, not standalone from within backend/.

VENV := .venv

.PHONY: backend-install backend-run backend-test

backend-install:
	uv pip install --python $(VENV)/bin/python -r backend/requirements.txt

backend-run:
	$(VENV)/bin/uvicorn backend.app:app --reload --port 8000

backend-test:
	$(VENV)/bin/pytest backend/tests
