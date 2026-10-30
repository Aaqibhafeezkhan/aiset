"""python -m aiset.run <issue> ...: the same as `aiset run <issue> ...`."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
