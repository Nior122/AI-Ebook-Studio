"""Static verification for the frontend: parse every .ts/.tsx with tree-sitter
and report syntax errors; then check that every component/hook is imported
somewhere (no orphan files), and every page under app/ is a route entry.
"""
import os
import re
import sys

from tree_sitter import Language, Parser
import tree_sitter_typescript

TSX = Language(tree_sitter_typescript.language_tsx())
TS = Language(tree_sitter_typescript.language_typescript())

ROOT = "/home/user/repos/AI-Ebook-Studio/frontend"

parser_tsx = Parser(TSX)
parser_ts = Parser(TS)


def parse_file(path):
    source = open(path, "rb").read()
    parser = parser_tsx if path.endswith(".tsx") else parser_ts
    tree = parser.parse(source)
    errors = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "ERROR" or node.is_missing:
            errors.append((node.start_point, node.type, source[node.start_byte:node.end_byte][:60]))
        stack.extend(node.children)
    return errors


def main():
    tsx_errors = []
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".next", ".git")]
        for name in filenames:
            if name.endswith((".ts", ".tsx")) and not name.endswith(".d.ts"):
                files.append(os.path.join(dirpath, name))

    print(f"Parsing {len(files)} files…")
    for path in sorted(files):
        try:
            errors = parse_file(path)
        except Exception as exc:  # noqa: BLE001
            tsx_errors.append((path, f"parse crash: {exc}"))
            continue
        if errors:
            tsx_errors.append((path, errors[:5]))

    if tsx_errors:
        print("\n=== SYNTAX ERRORS ===")
        for path, errors in tsx_errors:
            print(f"\n{os.path.relpath(path, ROOT)}")
            for err in errors[:5]:
                print(f"   {err}")
    else:
        print("✓ All files parse cleanly")

    # ---- import wiring scan ----
    # Build the import graph: file -> set of imported module specifiers (relative or alias).
    def imports_of(path):
        source = open(path, encoding="utf-8").read()
        found = set()
        for match in re.finditer(r"from\s+[\"']([^\"']+)[\"']", source):
            spec = match.group(1)
            if spec.startswith("."):
                base = os.path.dirname(path)
                if spec.endswith(".tsx") or spec.endswith(".ts"):
                    candidate = os.path.normpath(os.path.join(base, spec))
                else:
                    candidate = os.path.normpath(os.path.join(base, spec))
                    for ext in (".tsx", ".ts", "/index.tsx", "/index.ts"):
                        if os.path.exists(candidate + ext):
                            candidate = candidate + ext
                            break
                found.add(os.path.normpath(candidate))
            elif spec.startswith("@/"):
                candidate = os.path.normpath(os.path.join(ROOT, spec[2:]))
                resolved = candidate
                if os.path.isfile(candidate):
                    resolved = candidate
                else:
                    for ext in (".tsx", ".ts"):
                        if os.path.isfile(candidate + ext):
                            resolved = candidate + ext
                            break
                    else:
                        for index in ("/index.tsx", "/index.ts"):
                            if os.path.isfile(candidate + index):
                                resolved = candidate + index
                                break
                found.add(resolved)
        return found

    graph = {}
    for path in files:
        graph[path] = imports_of(path)

    # Everything under components/, hooks/, lib/ must be reachable from app/ or from
    # another reachable file; report unreachable files (excluding app/ routes, tests, config).
    reachable = set()
    queue = [path for path in files if os.path.relpath(path, ROOT).startswith("app/")]
    while queue:
        current = queue.pop()
        if current in reachable or not os.path.exists(current):
            continue
        reachable.add(current)
        for child in graph.get(current, set()):
            if os.path.exists(child):
                queue.append(child)

    orphans = []
    for path in sorted(files):
        rel = os.path.relpath(path, ROOT)
        if rel.startswith(("app/", "tests/", "vitest", "next-env")):
            continue
        if "/node_modules/" in path:
            continue
        if path not in reachable:
            # allow config files
            if rel.startswith(("eslint", "tailwind", "postcss", "tsconfig")):
                continue
            orphans.append(rel)

    if orphans:
        print("\n=== POTENTIALLY UNUSED FILES ===")
        for rel in orphans:
            print("  ", rel)
    else:
        print("✓ No orphan components/hooks/libs")

    # ---- routes sanity ----
    route_pages = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "app")):
        for name in filenames:
            if name == "page.tsx":
                route_pages.append(os.path.relpath(os.path.join(dirpath, name), ROOT))
    print(f"\n=== ROUTES ({len(route_pages)}) ===")
    for route in sorted(route_pages):
        print("  ", route)

    sys.exit(1 if tsx_errors else 0)


if __name__ == "__main__":
    main()
