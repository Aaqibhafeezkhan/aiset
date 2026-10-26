"""Atomic text writes keep the previous file when a staged write fails."""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from aiset import atomic  # noqa: E402


class PartialWriter:
    def __init__(self, stream):
        self.stream = stream

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stream.close()

    def write(self, text):
        self.stream.write(text[:4])
        raise OSError("simulated partial write failure")


class AtomicWriteTest(unittest.TestCase):
    def test_failed_partial_write_keeps_old_file_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("old settings\n")

            real_fdopen = atomic.os.fdopen

            def partial_fdopen(fd, *args, **kwargs):
                return PartialWriter(real_fdopen(fd, *args, **kwargs))

            with patch.object(atomic.os, "fdopen", side_effect=partial_fdopen):
                with self.assertRaisesRegex(OSError, "simulated partial write failure"):
                    atomic.write_text_atomic(path, "new settings\n", newline="\n")

            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "old settings\n")
            self.assertEqual(os.listdir(directory), ["settings.json"])

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_replacement_preserves_existing_permission_bits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("old\n")
            os.chmod(path, 0o640)

            atomic.write_text_atomic(path, "new\n", newline="\n")

            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o640)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_new_file_uses_mode_filtered_by_the_active_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "new.txt")
            source = os.path.join(os.path.dirname(__file__), "..", "src")
            script = (
                "import os, sys\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "os.umask(0o027)\n"
                "from aiset.atomic import write_text_atomic\n"
                "write_text_atomic(sys.argv[2], 'new')\n"
            )

            subprocess.run([sys.executable, "-c", script, source, path], check=True)

            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o640)

    def test_retries_windows_permission_error_before_replacing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("old\n")
            real_replace = atomic.os.replace
            attempts = 0

            def replace_after_lock(source, destination):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError("locked")
                return real_replace(source, destination)

            with patch.object(atomic.os, "name", "nt"):
                with patch.object(
                    atomic.os,
                    "replace",
                    side_effect=replace_after_lock,
                ) as replace:
                    with patch.object(atomic.time, "sleep") as sleep:
                        atomic.write_text_atomic(path, "new\n", newline="\n")

            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "new\n")
            self.assertEqual(replace.call_count, 2)
            sleep.assert_called_once_with(0.05)
            self.assertEqual(os.listdir(directory), ["settings.json"])

    def test_failed_windows_retries_preserve_original_and_remove_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("old\n")

            with patch.object(atomic.os, "name", "nt"):
                with patch.object(
                    atomic.os,
                    "replace",
                    side_effect=PermissionError("locked"),
                ) as replace:
                    with patch.object(atomic.time, "sleep") as sleep:
                        with self.assertRaises(PermissionError):
                            atomic.write_text_atomic(path, "new\n", newline="\n")

            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "old\n")
            self.assertEqual(replace.call_count, 4)
            self.assertEqual(sleep.call_count, 3)
            self.assertEqual(os.listdir(directory), ["settings.json"])


if __name__ == "__main__":
    unittest.main()
