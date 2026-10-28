"""Conexões temporárias com transação e fechamento explícito em qualquer SO."""
from contextlib import contextmanager
import sqlite3


@contextmanager
def sqlite_transaction(*args, **kwargs):
    connection = sqlite3.connect(*args, **kwargs)
    try:
        with connection:
            yield connection
    finally:
        # O context manager nativo faz commit/rollback, mas não fecha o arquivo.
        connection.close()
