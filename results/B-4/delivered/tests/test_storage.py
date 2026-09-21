import os
import sqlite3
import tempfile
import unittest

import fidx


class TestTokens(unittest.TestCase):
    def test_case_folding(self):
        self.assertEqual(fidx.tokens("Casa CASA casa"), {"casa"})

    def test_accented_word(self):
        self.assertEqual(fidx.tokens("Orçamento"), {"orçamento"})

    def test_digits(self):
        self.assertEqual(fidx.tokens("valor2024"), {"valor2024"})

    def test_punctuation_is_separator(self):
        self.assertEqual(
            fidx.tokens("casa, jardim; sol."), {"casa", "jardim", "sol"}
        )


class TestOpenIndex(unittest.TestCase):
    def test_reopen_reuses_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = fidx.open_index(directory)
            conn.execute(
                "INSERT INTO files (path, digest) VALUES (?, ?)", ("a.txt", "abc")
            )
            conn.commit()
            conn.close()

            self.assertTrue(os.path.isfile(fidx.index_path(directory)))

            conn2 = fidx.open_index(directory)
            row = conn2.execute(
                "SELECT path, digest FROM files WHERE path = ?", ("a.txt",)
            ).fetchone()
            self.assertEqual(row, ("a.txt", "abc"))
            self.assertEqual(
                conn2.execute("PRAGMA user_version").fetchone()[0],
                fidx.SCHEMA_VERSION,
            )
            conn2.close()


class TestSchemaVersionMismatch(unittest.TestCase):
    def test_mismatched_version_is_discarded_and_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            index_dir = os.path.join(directory, ".fidx")
            os.makedirs(index_dir)
            db_path = os.path.join(index_dir, "index.sqlite3")

            stale = sqlite3.connect(db_path)
            stale.execute(
                "CREATE TABLE files (path TEXT PRIMARY KEY, digest TEXT NOT NULL)"
            )
            stale.execute("INSERT INTO files (path, digest) VALUES ('old.txt', 'zzz')")
            stale.execute("PRAGMA user_version = 99")
            stale.commit()
            stale.close()

            conn = fidx.open_index(directory)

            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0],
                fidx.SCHEMA_VERSION,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM files").fetchone()[0], 0
            )
            conn.execute("INSERT INTO postings (term, path) VALUES ('x', 'a.txt')")
            conn.commit()
            conn.close()


if __name__ == "__main__":
    unittest.main()
