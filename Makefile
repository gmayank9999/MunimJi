PY := python
BACKEND := backend
FRONTEND := frontend

.PHONY: setup dev-backend dev-frontend dev test lint seed reset smoke decision-table chaos-test e2e

setup:
	cd $(BACKEND) && $(PY) -m venv .venv
	cd $(BACKEND) && .venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt || .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
	cd $(FRONTEND) && npm install

dev-backend:
	cd $(BACKEND) && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd $(FRONTEND) && npm run dev

dev:
	@echo "run 'make dev-backend' and 'make dev-frontend' in separate terminals"

test:
	cd $(BACKEND) && pytest -q

lint:
	cd $(BACKEND) && ruff check app tests scripts

seed:
	cd $(BACKEND) && $(PY) scripts/seed_paypal.py
	cd $(BACKEND) && $(PY) scripts/seed_gmail.py
	cd $(BACKEND) && $(PY) scripts/seed_notion.py

reset:
	cd $(BACKEND) && $(PY) scripts/demo_reset.py

smoke:
	cd $(BACKEND) && $(PY) scripts/smoke_swytchcode.py

decision-table:
	cd $(BACKEND) && $(PY) -m app.policy.explain --write-docs

chaos-test:
	cd $(BACKEND) && $(PY) scripts/chaos_test.py

e2e:
	cd $(BACKEND) && $(PY) scripts/e2e.py
