"""Check the call-count-based function naming rule for network.runtime.

Run with ``python check.py`` from any directory.  The checker reports every
function in ``src/m1/network/runtime.py`` whose name shape does not match the
number of lexical call sites found in this repository.
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNTIME_PATH = ROOT / "src" / "m1" / "network" / "runtime.py"
PREFIXES = {"handle", "on", "is", "has", "should", "may"}


def function_names_in_runtime():
    """Return the module-level functions that this rule can rename."""
    tree = ast.parse(RUNTIME_PATH.read_text(encoding="utf-8"), filename=str(RUNTIME_PATH))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not (node.name.startswith("__") and node.name.endswith("__"))
    }


def meaningful_word_count(name):
    """Count name words using the style card's private/question prefixes."""
    words = [word for word in name.lstrip("_").split("_") if word]
    if words and words[0] in PREFIXES:
        words.pop(0)
    return len(words)


class CallCollector(ast.NodeVisitor):
    def __init__(self, names, path):
        self.names = names
        self.path = path
        self.calls = defaultdict(list)

    def visit_Call(self, node):
        called_name = None
        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # This covers module aliases such as ``network.import_file(...)``.
            called_name = node.func.attr
        if called_name in self.names:
            self.calls[called_name].append((self.path, node.lineno))
        self.generic_visit(node)


def find_call_sites(names):
    """Find direct and module-attribute call expressions in repository Python."""
    calls = defaultdict(list)
    for path in ROOT.rglob("*.py"):
        if any(part in {".git", ".pytest_cache", "__pycache__"} for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as error:
            print(f"warning: could not inspect {path}: {error}", file=sys.stderr)
            continue
        collector = CallCollector(names, path)
        collector.visit(tree)
        for name, sites in collector.calls.items():
            calls[name].extend(sites)
    return calls


def main():
    names = function_names_in_runtime()
    calls = find_call_sites(names)
    errors = []
    for name in sorted(names):
        observed_count = len(calls[name])
        # Public functions are part of the module's API.  Their callers may
        # live outside this checkout, so treat them as reusable even when the
        # local source has few or no call expressions.
        count = observed_count if name.startswith("_") else max(observed_count, 2)
        words = meaningful_word_count(name)
        if count <= 1 and words < 3:
            errors.append(f"{name}: {count} call site(s); one-off functions need at least 3 meaningful words")
        elif count > 1 and words not in (1, 2):
            errors.append(f"{name}: {count} call sites; reusable functions need 1 or 2 meaningful words")

    if not errors:
        print("Function naming check passed.")
        return 0
    print("Function naming check failed:")
    for error in errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
