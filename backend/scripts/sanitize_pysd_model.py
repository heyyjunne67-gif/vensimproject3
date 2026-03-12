from __future__ import annotations

from pathlib import Path
import argparse
import re


def sanitize_lookup_add_blocks(source: str) -> str:
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    in_add_block = False
    paren_depth = 0

    for line in lines:
        if not in_add_block and ".add(" in line:
            in_add_block = True

        if in_add_block:
            line = re.sub(
                r'"([^\"]+)"\s*:',
                lambda m: m.group(0) if m.group(1) in {"Хүйс", "Нас"} else '"Нас":',
                line,
            )
            paren_depth += line.count("(") - line.count(")")
            if paren_depth <= 0:
                in_add_block = False
                paren_depth = 0

        out.append(line)

    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sanitize malformed coordinate keys in PySD model .py files")
    parser.add_argument("model_file", type=Path)
    args = parser.parse_args()

    path = args.model_file
    original = path.read_text(encoding="utf-8")
    sanitized = sanitize_lookup_add_blocks(original)

    if sanitized == original:
        print("No changes needed")
        return 0

    path.write_text(sanitized, encoding="utf-8")
    print("Sanitized:", str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
