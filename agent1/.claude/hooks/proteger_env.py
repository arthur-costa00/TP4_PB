"""Bloqueia edições de arquivos locais de ambiente feitas pelas ferramentas do Claude Code."""
import json
import sys
from pathlib import Path


def main():
    event = json.load(sys.stdin)
    path = event.get("tool_input", {}).get("file_path")
    if not isinstance(path, str) or not path:
        return 0

    candidate = Path(path)
    for name in (candidate.name, candidate.resolve().name):
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            print("Edição de arquivo local de ambiente bloqueada pelo hook do Agente 1.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
