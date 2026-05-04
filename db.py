from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

_DB_PATH = Path(__file__).parent / "foodapp.db"
_engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})
Base.metadata.create_all(_engine)
Session = sessionmaker(bind=_engine)


def get_session():
    return Session()
