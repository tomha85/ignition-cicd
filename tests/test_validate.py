import unittest
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate import validate

class TestValidate(unittest.TestCase):
    def test_empty_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                validate(d)

    def test_minimal_source(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / 'project.json').write_text('{}')
            (p / 'resource.json').write_text('{}')
            self.assertEqual(validate(p), 2)

if __name__ == '__main__':
    unittest.main()
