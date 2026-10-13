"""Standalone CLI. Deliberately avoid creating bytecode in the tool tree."""

import sys

sys.dont_write_bytecode = True

from rulecheck.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
