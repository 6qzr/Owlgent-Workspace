
import os

import psycopg
from dotenv import load_dotenv
from psycopg import Connection

load_dotenv()


def get_connection() -> Connection:
    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
