import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slug import slugify  # noqa: E402


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_punctuation(self):
        self.assertEqual(slugify("Stage gates: stop the line!"), "stage-gates-stop-the-line")

    def test_spaces_collapse(self):
        self.assertEqual(slugify("  many   spaces  "), "many-spaces")

    def test_accents(self):
        self.assertEqual(slugify("Crème brûlée"), "creme-brulee")


if __name__ == "__main__":
    unittest.main()
