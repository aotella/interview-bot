# Frontend targets. Included from the root Makefile - run via `make
# frontend-*` from the repo root, not standalone from within frontend/.

.PHONY: frontend-install frontend-dev frontend-build frontend-lint frontend-preview

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-lint:
	cd frontend && npm run lint

frontend-preview:
	cd frontend && npm run preview
