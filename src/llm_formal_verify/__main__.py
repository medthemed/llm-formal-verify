"""Allow ``python -m llm_formal_verify``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
