"""Brain and live lookups read graph files for a single-repository unit."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aiset import brain  # noqa: E402


class BrainGraphFilesTest(unittest.TestCase):
    def test_hidden_root_unit_graph_is_merged_and_indexed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graphs = root / "graph"
            index = graphs / "index"
            code = root / "repos"
            knowledge = root / "knowledge"
            episodes = root / "episodes"
            index.mkdir(parents=True)
            code.mkdir()
            knowledge.mkdir()
            episodes.mkdir()

            graph = {
                "nodes": [
                    {
                        "id": "file:./app.py",
                        "type": "file",
                        "label": "app.py",
                        "repo": ".",
                        "rel": "app.py",
                        "path": str(code / "app.py"),
                    }
                ],
                "edges": [],
            }
            (graphs / "..json").write_text(json.dumps(graph))
            index_data = {
                "files": {"app.py": {"data": {"symbols": [{"name": "hello"}]}}}
            }
            (index / "..json").write_text(json.dumps(index_data))

            brain._cache.clear()
            try:
                with (
                    patch.object(brain, "GRAPHS", str(graphs)),
                    patch.object(brain, "CODE_ROOT", str(code)),
                    patch.object(brain, "KNOWLEDGE", str(knowledge)),
                    patch.object(brain, "EPISODES", str(episodes)),
                ):
                    result = brain.build(
                        SimpleNamespace(window=86400, scan=lambda: []), {"members": []}
                    )
                    groups = {group["id"]: group for group in result["tree"]}
                    code_group = groups.get("group:code")
                    self.assertIsNotNone(code_group)
                    self.assertEqual(code_group["children"][0]["id"], "graph:.")
                    self.assertEqual(
                        [node["id"] for node in brain._graph_nodes()["file"]],
                        ["file:./app.py"],
                    )
                    self.assertEqual(brain._symbol_files()["hello"], [(".", "app.py")])
            finally:
                brain._cache.clear()


if __name__ == "__main__":
    unittest.main()
