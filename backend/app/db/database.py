from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

Base = declarative_base()

engine = create_engine(get_settings().database_url, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        # Ensure legacy-compatible column exists. SQLite does not support
        # `ALTER TABLE IF EXISTS ... ADD COLUMN IF NOT EXISTS`, so inspect
        # the table first and add the column only when missing.
        try:
            # If using SQLite the PRAGMA check is used to add missing columns
            if str(engine.url).startswith("sqlite"):
                result = connection.execute(text("PRAGMA table_info('projects')"))
                cols = [row[1] for row in result]
                if "file_contents" not in cols:
                    connection.execute(
                        text("ALTER TABLE projects ADD COLUMN file_contents TEXT DEFAULT '{}' ")
                    )
                if "pipeline_state" not in cols:
                    connection.execute(
                        text("ALTER TABLE projects ADD COLUMN pipeline_state TEXT DEFAULT '{}' ")
                    )
                if "generated_code" not in cols:
                    connection.execute(
                        text("ALTER TABLE projects ADD COLUMN generated_code TEXT DEFAULT '' ")
                    )
                if "generated_tests" not in cols:
                    connection.execute(
                        text("ALTER TABLE projects ADD COLUMN generated_tests TEXT DEFAULT '' ")
                    )
                if "behavior_graph" not in cols:
                    connection.execute(
                        text("ALTER TABLE projects ADD COLUMN behavior_graph TEXT DEFAULT '{}' ")
                    )
            else:
                # For Postgres ensure pgvector (vector) extension exists for vector column support
                try:
                    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                except Exception:
                    # Some managed DBs may restrict extension creation; ignore if not allowed
                    pass
        except Exception:
            # Best-effort: ignore failures during migration in dev environments.
            pass
