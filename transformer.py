from sqlalchemy import Connection
from typing import Dict


def executeTransformer(conn: Connection, tableMapping: Dict[str, str]) -> None:
    print(f"Executing transformer with {tableMapping}")
