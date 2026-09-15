.PHONY: test dev-api dev-web deploy logs

test:
	cd backend && uv run ruff check . && uv run pytest
	cd frontend && npm test && npm run build
	python3 -m unittest discover -s tests/deploy -v

dev-api:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	cd frontend && npm run dev -- --host 127.0.0.1

deploy:
	./deploy

logs:
	docker compose logs -f --tail=100
