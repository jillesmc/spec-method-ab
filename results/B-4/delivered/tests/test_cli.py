import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write(directory, relpath, content):
    full_path = os.path.join(directory, relpath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return full_path


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "fidx", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


class TestIndexAndSearchThroughSubprocess(unittest.TestCase):
    def test_index_then_search_reports_matching_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa jardim")
            write(directory, "b.txt", "casa sol")
            write(directory, "c.txt", "lua estrela")

            index_result = run_cli(directory, "index")
            self.assertEqual(index_result.returncode, 0, index_result.stderr)

            search_result = run_cli(directory, "search", "casa")
            self.assertEqual(search_result.returncode, 0, search_result.stderr)
            self.assertEqual(
                search_result.stdout.splitlines(), ["a.txt", "b.txt"]
            )


class TestIndexReportsRefreshCounts(unittest.TestCase):
    def test_one_changed_file_is_reflected_in_the_report(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa")
            write(directory, "b.txt", "jardim")
            run_cli(directory, "index")

            write(directory, "a.txt", "casa nova")
            result = run_cli(directory, "index")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("seen=2", result.stdout)
            self.assertIn("reprocessed=1", result.stdout)
            self.assertIn("removed=0", result.stdout)


class TestExitCodes(unittest.TestCase):
    def test_search_match_exits_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa")
            run_cli(directory, "index")

            result = run_cli(directory, "search", "casa")
            self.assertEqual(result.returncode, 0)

    def test_search_no_match_exits_one_with_empty_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa")
            run_cli(directory, "index")

            result = run_cli(directory, "search", "inexistente")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")

    def test_missing_directory_exits_two_on_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = os.path.join(directory, "nao-existe")

            result = run_cli(missing, "search", "casa")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertNotEqual(result.stderr, "")

    def test_missing_index_exits_two_on_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_cli(directory, "search", "casa")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("index", result.stderr)

    def test_empty_query_term_exits_two_on_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, "a.txt", "casa")
            run_cli(directory, "index")

            result = run_cli(directory, "search", "   ")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertNotEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
