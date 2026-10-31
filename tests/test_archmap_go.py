"""Architecture view: a Go service's framework and infrastructure come from go.mod."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import archmap  # noqa: E402

GO_MOD = """module example.com/shop

go 1.22

require github.com/labstack/echo/v5 v5.0.0

require (
\tgithub.com/jackc/pgx/v5 v5.5.0
\tgithub.com/rabbitmq/amqp091-go v1.9.0
\tgithub.com/redis/go-redis/v9 v9.5.1 // indirect
)

replace github.com/go-sql-driver/mysql => ../mysql v1.8.0

replace (
\tgo.mongodb.org/mongo-driver/v2 => ../mongo v2.0.0
)
"""


class GoModTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = tmp.name
        self.repo = os.path.join(self.workspace, "shop")
        os.makedirs(self.repo)

    def scan(self, go_mod):
        with open(os.path.join(self.repo, "go.mod"), "w", encoding="utf-8", newline="\n") as f:
            f.write(go_mod)
        with patch.object(archmap, "CODE_ROOT", self.workspace):
            return archmap.scan_repo("shop")

    def test_framework_and_components_from_direct_requirements(self):
        result = self.scan(GO_MOD)

        self.assertEqual(result["framework"], "Echo")  # echo/v5: the major suffix is ignored
        components = {c["id"]: c for c in result["components"]}
        self.assertIn("postgres", components)
        self.assertIn("rabbitmq", components)
        self.assertNotIn("redis", components)  # only an indirect requirement
        self.assertNotIn("mysql", components)  # only replaced, never required
        self.assertNotIn("mongodb", components)  # only in a replace block
        evidence = components["postgres"]["evidence"][0]
        self.assertEqual((evidence["file"], evidence["line"]), ("go.mod", 8))

    def test_single_line_require_of_a_framework(self):
        result = self.scan("module example.com/api\n\nrequire github.com/gin-gonic/gin v1.10.0\n")

        self.assertEqual(result["framework"], "Gin")


if __name__ == "__main__":
    unittest.main()
