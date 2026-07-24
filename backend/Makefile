# Argi backend — migration + test helpers.
#
# DATABASE_URL / TEST_DATABASE_URL come from the environment (or .env). The
# test targets default the test DSN to the compose Postgres `argi_test` db.

TEST_DATABASE_URL ?= postgresql+asyncpg://argi:argi_dev_password@db:5432/argi_test

.PHONY: migrate makemigrations downgrade test test-unit test-integration test-streaming cov

## Apply all pending migrations.
migrate:
	alembic upgrade head

## Generate a migration from model changes:  make makemigrations m="add x"
makemigrations:
	alembic revision --autogenerate -m "$(m)"

## Roll back the most recent migration.
downgrade:
	alembic downgrade -1

## Run the whole test suite.
test:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) pytest -q

## Unit tests only.
test-unit:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) pytest -q -m unit

test-integration:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) pytest -q -m integration

test-streaming:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) pytest -q -m streaming

## Coverage report over app/.
cov:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) coverage run -m pytest -q && coverage report -m
