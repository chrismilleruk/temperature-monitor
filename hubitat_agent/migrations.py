import os
import logging
import psycopg2
from pathlib import Path

logger = logging.getLogger("migrations")


def run_migrations():
    """Run all SQL migrations from the migrations directory."""
    dsn = os.getenv("TIMESCALEDB_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("TIMESCALEDB_URL or DATABASE_URL must be set to run migrations")

    # Find migration files in the migrations directory alongside this script
    script_dir = Path(__file__).parent
    migrations_dir = script_dir / "migrations"

    if not migrations_dir.exists():
        logger.warning("Migrations directory does not exist: %s", migrations_dir)
        return

    # Get sorted migration files
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        logger.info("No migration files found")
        return

    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                for migration_file in migration_files:
                    logger.info("Running migration: %s", migration_file.name)
                    with open(migration_file, "r") as f:
                        sql = f.read()
                    cur.execute(sql)
        logger.info("All migrations completed successfully")
    except Exception as e:
        logger.exception("Migration failed: %s", e)
        raise
    finally:
        conn.close()
