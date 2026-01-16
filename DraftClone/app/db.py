from pathlib import Path

from sqlmodel import Session, create_engine

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.sqlite"
engine = create_engine(f"sqlite:///{DATABASE_PATH}", echo=False)


def get_session() -> Session:
    return Session(engine)
