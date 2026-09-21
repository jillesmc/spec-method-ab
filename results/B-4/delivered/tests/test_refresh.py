import os
import sqlite3
import tempfile
import unittest

import fidx


def write(directory, relpath, content):
    full_path = os.path.join(directory, relpath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return full_path


def indexed_paths(directory):
    conn = sqlite3.connect(fidx.index_path(directory))
    try:
        return {row[0] for row in conn.execute("SELECT path FROM files")}
    finally:
        conn.close()


def paths_for_term(directory, term):
    conn = sqlite3.connect(fidx.index_path(directory))
    try:
        rows = conn.execute(
            "SELECT path FROM postings WHERE term = ?", (term,)
        ).fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


class TestWalkSkipsHidden(unittest.TestCase):
    def test_hidden_entries_are_never_indexed(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "visible")
            write(directory, ".git/config", "checkout metadata")
            write(directory, ".hidden.txt", "also hidden")

            stats = fidx.index_directory(directory)

            self.assertEqual(indexed_paths(directory), {"a.txt"})
            self.assertEqual(stats["seen"], 1)

    def test_fidx_storage_is_never_indexed(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "visible")
            fidx.index_directory(directory)

            stats = fidx.index_directory(directory)

            self.assertEqual(indexed_paths(directory), {"a.txt"})
            self.assertEqual(stats["seen"], 1)


class TestFirstRun(unittest.TestCase):
    def test_first_run_indexes_every_file(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa")
            write(directory, os.path.join("sub", "b.txt"), "jardim")

            stats = fidx.index_directory(directory)

            self.assertEqual(stats["seen"], 2)
            self.assertEqual(stats["reprocessed"], 2)
            self.assertEqual(stats["removed"], 0)
            self.assertEqual(stats["unreadable"], 0)
            self.assertEqual(
                indexed_paths(directory), {"a.txt", os.path.join("sub", "b.txt")}
            )


class TestRemoval(unittest.TestCase):
    def test_deleted_file_is_removed_and_unmatched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write(directory, "a.txt", "unique_term")
            fidx.index_directory(directory)
            self.assertEqual(paths_for_term(directory, "unique_term"), {"a.txt"})

            os.remove(path)
            stats = fidx.index_directory(directory)

            self.assertEqual(stats["removed"], 1)
            self.assertEqual(paths_for_term(directory, "unique_term"), set())
            self.assertNotIn("a.txt", indexed_paths(directory))


class TestUnreadableFile(unittest.TestCase):
    def test_unreadable_file_keeps_previous_entry(self):
        if os.geteuid() == 0:
            self.skipTest("chmod has no effect when running as root")
        with tempfile.TemporaryDirectory() as directory:
            path = write(directory, "a.txt", "term_a")
            write(directory, "b.txt", "term_b")
            fidx.index_directory(directory)

            os.chmod(path, 0o000)
            try:
                stats = fidx.index_directory(directory)
            finally:
                os.chmod(path, 0o644)

            self.assertEqual(stats["unreadable"], 1)
            self.assertEqual(stats["seen"], 2)
            self.assertEqual(stats["reprocessed"], 0)
            self.assertEqual(stats["removed"], 0)
            self.assertIn("a.txt", indexed_paths(directory))
            self.assertEqual(paths_for_term(directory, "term_a"), {"a.txt"})


class TestTimestampTrapA(unittest.TestCase):
    def test_content_change_with_older_mtime_is_reprocessed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write(directory, "a.txt", "old_content")
            fidx.index_directory(directory)
            self.assertEqual(paths_for_term(directory, "old_content"), {"a.txt"})

            with open(path, "w", encoding="utf-8") as fh:
                fh.write("new_content")
            past = os.stat(path).st_mtime - 100000
            os.utime(path, (past, past))

            stats = fidx.index_directory(directory)

            self.assertEqual(stats["reprocessed"], 1)
            self.assertEqual(paths_for_term(directory, "new_content"), {"a.txt"})
            self.assertEqual(paths_for_term(directory, "old_content"), set())


class TestTimestampTrapB(unittest.TestCase):
    def test_touched_mtime_without_content_change_is_not_reprocessed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write(directory, "a.txt", "same_content")
            fidx.index_directory(directory)

            future = os.stat(path).st_mtime + 100000
            os.utime(path, (future, future))

            stats = fidx.index_directory(directory)

            self.assertEqual(stats["reprocessed"], 0)


class TestMovedFile(unittest.TestCase):
    def test_moved_file_is_reported_only_at_new_path(self):
        with tempfile.TemporaryDirectory() as directory:
            old_path = write(directory, "old.txt", "moved_term")
            fidx.index_directory(directory)

            new_path = os.path.join(directory, "new.txt")
            os.rename(old_path, new_path)

            fidx.index_directory(directory)

            self.assertEqual(paths_for_term(directory, "moved_term"), {"new.txt"})
            self.assertNotIn("old.txt", indexed_paths(directory))
            self.assertIn("new.txt", indexed_paths(directory))


if __name__ == "__main__":
    unittest.main()
