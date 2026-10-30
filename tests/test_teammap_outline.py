"""Tests for teammap outline's indexed file skeleton output and CLI errors."""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TEAMMAP = os.path.join(HERE, "..", "src", "aiset", "teammap.py")


class TeammapOutlineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = self.tmp.name
        self.repo = os.path.join(self.ws, "shop")
        os.makedirs(os.path.join(self.repo, "app"))
        with open(os.path.join(self.repo, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write("[project]\nname = 'shop'\n")
        self.service = os.path.join(self.repo, "app", "service.py")
        source = (
            "import fastapi\n"
            "from sqlalchemy.orm import Session\n"
            "from .models import Order\n"
            "from .schemas import OrderIn\n"
            "\n"
            "app = fastapi.FastAPI()\n"
            "\n"
            "class OrderService:\n"
            "    def create(self, data: OrderIn, db: Session):\n"
            "        return data\n"
            "\n"
            "    def cancel(self, order_id: int):\n"
            "        return order_id\n"
            "\n"
            "@app.post('/api/orders')\n"
            "def place_order(data: OrderIn) -> Order:\n"
            "    return Order()\n"
        )
        with open(self.service, "w", encoding="utf-8") as f:
            f.write(source)
        subprocess.run(["git", "-C", self.repo, "init", "-q"], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=test@example.invalid",
                        "-c", "user.name=Test", "commit", "-qm", "fixture"], check=True, capture_output=True)
        team = os.path.join(self.ws, ".claude", "team")
        os.makedirs(team)
        with open(os.path.join(team, "roster.json"), "w", encoding="utf-8") as f:
            f.write('{"team":"test","members":[{"id":"engineer","name":"Test","role":"Engineer","repos":["shop"]}]}')
        self.env = dict(os.environ, AISET_WORKSPACE=self.ws)
        self.env.pop("MSYSTEM", None)

    def tearDown(self):
        self.tmp.cleanup()

    def run_teammap(self, *args):
        return subprocess.run([sys.executable, TEAMMAP, *args], cwd=self.ws, env=self.env,
                              capture_output=True, text=True, encoding="utf-8")

    def test_outline_shows_imports_nested_signatures_ranges_sizes_and_route(self):
        result = self.run_teammap("outline", "app/service.py")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("shop/app/service.py", output)
        self.assertIn("imports  fastapi, sqlalchemy.orm.Session, .models.Order, .schemas.OrderIn", output)
        self.assertIn("class OrderService", output)
        self.assertIn("def create(data: OrderIn, db: Session)", output)
        self.assertIn("def cancel(order_id: int)", output)
        self.assertIn("def place_order(data: OrderIn) -> Order", output)
        self.assertIn("route POST /api/orders → place_order()", output)
        self.assertRegex(output, r"OrderService\s+8-\d+ \(\d+\)")
        self.assertRegex(output, r"create\(data: OrderIn, db: Session\)\s+9-10 \(2\)")

    def test_unknown_file_exits_nonzero_with_message(self):
        result = self.run_teammap("outline", "missing.py")
        self.assertEqual(result.returncode, 4)
        self.assertIn("no file matches 'missing.py'", result.stdout + result.stderr)


    def test_exact_path_wins_over_substring_matches(self):
        os.makedirs(os.path.join(self.repo, "tests"))
        for rel in ("app/order_service.py", "tests/test_service.py"):
            path = os.path.join(self.repo, rel)
            with open(path, "w", encoding="utf-8") as f:
                f.write("def helper():\n    return 1\n")
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=test@example.invalid",
                        "-c", "user.name=Test", "commit", "-qm", "add similar filenames"],
                       check=True, capture_output=True)
        result = self.run_teammap("outline", "service.py")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("shop/app/service.py", output)
        self.assertNotIn("multiple files match", output)
        self.assertNotIn("order_service.py", output)
        self.assertNotIn("test_service.py", output)


    def test_ambiguous_file_lists_candidates_and_exits_three(self):
        other = os.path.join(self.repo, "other.py")
        with open(other, "w", encoding="utf-8") as f:
            f.write("def other():\n    return 1\n")
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=test@example.invalid",
                        "-c", "user.name=Test", "commit", "-qm", "second fixture"], check=True, capture_output=True)
        result = self.run_teammap("outline", ".py")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 3, output)
        self.assertIn("multiple files match", output)
        self.assertIn("shop/app/service.py", output)
        self.assertIn("shop/other.py", output)


if __name__ == "__main__":
    unittest.main()
