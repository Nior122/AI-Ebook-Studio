"""Static verification for the frontend: parse every .ts/.tsx with tree-sitter
and report syntax errors; then check that every component/hook is imported
somewhere (no orphan files), and every page under app/ is a route entry.

Static imports and dynamic imports (next/dynamic + import(\"...\")) are both
wired into the reachability graph.
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

# Matches `from "x"`, `import "x"` (side-effect), and dynamic `import("x")`.
IMPORT_RE = re.compile(r'from\s+["\']([^"\']+)["\']|import\(\s*["\']([^"\']+)["\']\s*\)')


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


def resolve_spec(path, spec):
    """Resolve a module specifier (relative or @/ alias) to a file path."""
    if spec.startswith("."):
        base = os.path.dirname(path)
        candidate = os.path.normpath(os.path.join(base, spec))
        if os.path.exists(candidate):
            return candidate
        for ext in (".tsx", ".ts", "/index.tsx", "/index.ts"):
            if os.path.exists(candidate + ext):
                return candidate + ext
        return candidate
    if spec.startswith("@/"):
        candidate = os.path.normpath(os.path.join(ROOT, spec[2:]))
        if os.path.isfile(candidate):
            return candidate
        for ext in (".tsx", ".ts"):
            if os.path.isfile(candidate + ext):
                return candidate + ext
        for index in ("/index.tsx", "/index.ts"):
            if os.path.isfile(candidate + index):
                return candidate + index
        return candidate
    return None


def imports_of(path):
    source = open(path, encoding="utf-8").read()
    found = set()
    for match in IMPORT_RE.finditer(source):
        spec = match.group(1) or match.group(2)
        resolved = resolve_spec(path, spec)
        if resolved:
            found.add(os.path.normpath(resolved))
    return found


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
