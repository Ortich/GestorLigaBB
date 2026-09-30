import os
from sqlmodel import SQLModel, create_engine, Session

DATABASE_FILE = os.environ.get("DATABASE_FILE", "bloodbowl.db")
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

connect_args = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
