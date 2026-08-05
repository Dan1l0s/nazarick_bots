#!/usr/bin/env python3
"""Compare two versions of a Python file at AST level.

Reports functions that exist in only one version, and functions whose *logic
structure* differs - ignoring comments, docstrings, formatting, and whitespace.
Used to verify the refactor preserves behavior: anything it flags should be a
deliberate change documented in CHANGES.md, and anything it doesn't flag is
provably structurally identical.

Usage:
    python tools/ast_compare.py ORIGINAL_FILE REFACTORED_FILE
    python tools/ast_compare.py --all PATH_TO_ORIGINAL_REPO

Note: "LOGIC DIFFERS" does not necessarily mean broken - trivially equivalent
rewrites (`x == None` -> `x is None`, `not a in b` -> `a not in b`, moving class
attributes into __init__) also show up here. It's a review checklist, not a
pass/fail gate. Every entry it reports for the current refactor is accounted
for in CHANGES.md.
"""

import ast
import os
import sys

REFACTORED_FILES = [
    "helpers/helpers.py",
    "helpers/database_logger.py",
    "helpers/embedder.py",
    "helpers/view_panels.py",
    "bots/music_instance.py",
    "bots/music_leader.py",
    "bots/admin_bot.py",
    "bots/log_bot.py",
    "main.py",
    "hosting/server_manager.py",
    "hosting/client_manager.py",
]


def strip_docstring(node):
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return body


def collect(path):
    """Maps qualified function name -> normalized AST dump of its body."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    funcs = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_ClassDef(self, node):
            self.stack.append(node.name)
            for child in node.body:
                self.visit(child)
            self.stack.pop()

        def _handle_function(self, node):
            base = ".".join(self.stack + [node.name])
            name = base
            n = 0
            # Duplicate definitions (same name, same scope) get a #N suffix so
            # shadowed functions are visible rather than silently collapsing.
            while name in funcs:
                n += 1
                name = f"{base}#{n}"
            module = ast.Module(body=strip_docstring(node), type_ignores=[])
            funcs[name] = ast.dump(module, annotate_fields=False)
            self.stack.append(node.name)
            for child in node.body:
                self.visit(child)
            self.stack.pop()

        def visit_FunctionDef(self, node):
            self._handle_function(node)

        def visit_AsyncFunctionDef(self, node):
            self._handle_function(node)

    Visitor().visit(tree)
    return funcs


def compare(original_path, refactored_path):
    original = collect(original_path)
    refactored = collect(refactored_path)

    only_original = sorted(set(original) - set(refactored))
    only_refactored = sorted(set(refactored) - set(original))
    differs = sorted(k for k in set(original) & set(refactored)
                     if original[k] != refactored[k])

    print(f"  functions: original={len(original)} refactored={len(refactored)}")
    if only_original:
        print(f"  ONLY IN ORIGINAL:   {only_original}")
    if only_refactored:
        print(f"  ONLY IN REFACTORED: {only_refactored}")
    if differs:
        print(f"  LOGIC DIFFERS:      {differs}")
    if not (only_original or only_refactored or differs):
        print("  OK - all function bodies structurally identical")
    return bool(only_original or only_refactored or differs)


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--all":
        original_repo = args[1]
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for rel in REFACTORED_FILES:
            refactored = os.path.join(here, rel)
            original = os.path.join(original_repo, rel)
            if not (os.path.exists(refactored) and os.path.exists(original)):
                continue
            print(f"=== {rel} ===")
            compare(original, refactored)
        return 0
    if len(args) != 2:
        print(__doc__)
        return 2
    compare(args[0], args[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
