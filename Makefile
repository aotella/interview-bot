include backend/backend.mk
include frontend/frontend.mk

.PHONY: install test lint build up down podman-up podman-down

install: backend-install frontend-install

test: backend-test

lint: frontend-lint

build: frontend-build

up:
	docker compose up -d --build

down:
	docker compose down

podman-up:
	podman-compose -f podman-compose.yml up -d --build

podman-down:
	podman-compose -f podman-compose.yml down
