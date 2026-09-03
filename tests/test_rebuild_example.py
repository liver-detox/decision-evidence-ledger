import os
import subprocess
import sys
import unittest
from pathlib import Path


class RebuildSyntheticChainExampleTest(unittest.TestCase):
    def test_example_rebuilds_the_checked_in_chain(self):
        root = Path(__file__).parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "examples/rebuild_synthetic_chain.py")],
            cwd=root,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONPATH": str(root / "src")},
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(result.stderr, b"")
        self.assertEqual(
            result.stdout,
            (root / "examples/SYNTHETIC_chain.jsonl").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
