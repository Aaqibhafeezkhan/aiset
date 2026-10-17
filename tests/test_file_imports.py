"""teammap.file_imports: Python and TypeScript imports between files of one repo, tsconfig aliases included."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import teammap  # noqa: E402


def py(*imports):
    return {"lang": "py", "data": {"imports": [dict(zip(("module", "level", "name"), i)) for i in imports]}}


def ts(*specs):
    return {"lang": "ts", "data": {"imports": [{"from": s} for s in specs]}}


class FileImportsTest(unittest.TestCase):
    def test_python(self):
        repo = {"root": "/nowhere", "files": {
            "app/main.py": py(("app.services", 0, "billing"), ("fastapi", 0, "FastAPI")),
            "app/services/billing.py": py(("models", 2, "Invoice"), (None, 1, "util")),
            "app/services/util.py": py(),
            "app/models/__init__.py": py(),
        }}
        self.assertEqual(teammap.file_imports(repo), {
            ("app/main.py", "app/services/billing.py"),
            ("app/services/billing.py", "app/models/__init__.py"),
            ("app/services/billing.py", "app/services/util.py"),
        })

    def test_typescript_with_tsconfig_alias(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "tsconfig.json"), "w") as f:
                f.write('{\n  // comments are allowed\n  "compilerOptions": { "paths": { "@/*": ["./*"] } },\n}')
            repo = {"root": root, "files": {
                "app/page.tsx": ts("@/lib/api", "./parts", "react"),
                "app/parts/index.tsx": ts("../../lib/api/client"),
                "lib/api.ts": ts(),
                "lib/api/client.ts": ts(),
            }}
            self.assertEqual(teammap.tsconfig_aliases(root), [("@/", "")])
            self.assertEqual(teammap.file_imports(repo), {
                ("app/page.tsx", "lib/api.ts"),
                ("app/page.tsx", "app/parts/index.tsx"),
                ("app/parts/index.tsx", "lib/api/client.ts"),
            })


if __name__ == "__main__":
    unittest.main()
