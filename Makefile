.PHONY: up down logs status test

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

status:
	docker compose ps

test:
	docker compose exec api pytest
