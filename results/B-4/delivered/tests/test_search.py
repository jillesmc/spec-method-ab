import os
import tempfile
import unittest

import fidx


def write(directory, relpath, content):
    full_path = os.path.join(directory, relpath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return full_path


class TestSearchMatching(unittest.TestCase):
    def test_two_of_three_files(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa jardim")
            write(directory, "b.txt", "casa sol")
            write(directory, "c.txt", "lua estrela")
            fidx.index_directory(directory)

            self.assertEqual(fidx.search(directory, "casa"), ["a.txt", "b.txt"])

    def test_repeated_term_in_one_file_reported_once(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa casa casa")
            fidx.index_directory(directory)

            self.assertEqual(fidx.search(directory, "casa"), ["a.txt"])

    def test_case_mismatched_query(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "Orçamento anual")
            fidx.index_directory(directory)

            self.assertEqual(fidx.search(directory, "orçamento"), ["a.txt"])

    def test_two_word_query_requires_both_terms(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa jardim")
            write(directory, "b.txt", "casa sol")
            fidx.index_directory(directory)

            self.assertEqual(fidx.search(directory, "casa jardim"), ["a.txt"])

    def test_no_match_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa")
            fidx.index_directory(directory)

            self.assertEqual(fidx.search(directory, "inexistente"), [])

    def test_empty_query_term_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa")
            fidx.index_directory(directory)

            with self.assertRaises(ValueError):
                fidx.search(directory, "   ")


class TestSearchIsReadOnly(unittest.TestCase):
    def test_unreadable_corpus_still_matches_and_next_index_reprocesses_nothing(self):
        if os.geteuid() == 0:
            self.skipTest("chmod has no effect when running as root")
        with tempfile.TemporaryDirectory() as directory:
            path = write(directory, "a.txt", "unique_term")
            fidx.index_directory(directory)

            os.chmod(path, 0o000)
            try:
                self.assertEqual(fidx.search(directory, "unique_term"), ["a.txt"])
                stats = fidx.index_directory(directory)
            finally:
                os.chmod(path, 0o644)

            self.assertEqual(stats["reprocessed"], 0)


class TestSearchMissingIndex(unittest.TestCase):
    def test_missing_index_raises_error_naming_index_command(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(fidx.IndexNotFoundError) as ctx:
                fidx.search(directory, "casa")

            self.assertIn("index", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
