.PHONY: up down backend-test frontend-check migrate superuser

up:
	docker compose up --build

down:
	docker compose down

backend-test:
	docker compose run --rm api pytest

frontend-check:
	cd frontend && npm run lint && npm run typecheck

migrate:
	docker compose run --rm api python manage.py migrate

superuser:
	docker compose run --rm api python manage.py createsuperuser

