from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    base = Path(__file__).resolve().parents[1] / "sql"
    sql_files = [base / "001_init.sql", base / "002_rankings.sql"]

    with engine.begin() as conn:
        for file in sql_files:
            sql = file.read_text(encoding="utf-8")
            conn.execute(text(sql))
    print("Database initialized")


if __name__ == "__main__":
    main()
