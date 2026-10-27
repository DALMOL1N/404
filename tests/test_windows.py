"""Regressões de portabilidade do SQLite e do banco de fusos horários."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from database import sqlite_transaction


class PortabilityTests(unittest.TestCase):
    def test_connection_commits_and_closes_before_file_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'with spaces.db'
            with sqlite_transaction(path) as connection:
                connection.execute('CREATE TABLE sample (value INTEGER)')
                connection.execute('INSERT INTO sample VALUES (42)')
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')
            with sqlite_transaction(path) as check:
                self.assertEqual(check.execute('SELECT value FROM sample').fetchone()[0], 42)
            # O Windows recusa remover um arquivo ainda aberto.
            path.unlink()
            self.assertFalse(path.exists())

    def test_connection_rolls_back_and_closes_on_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rollback.db'
            with sqlite_transaction(path) as connection:
                connection.execute('CREATE TABLE sample (value INTEGER)')
            with self.assertRaisesRegex(RuntimeError, 'simulado'):
                with sqlite_transaction(path) as connection:
                    connection.execute('INSERT INTO sample VALUES (42)')
                    raise RuntimeError('simulado')
            with sqlite_transaction(path) as check:
                self.assertEqual(check.execute('SELECT COUNT(*) FROM sample').fetchone()[0], 0)
            path.unlink()

    def test_sao_paulo_timezone_available(self):
        self.assertEqual(ZoneInfo('America/Sao_Paulo').key, 'America/Sao_Paulo')
