#!/usr/bin/env python3
"""
Enrich starter_code for every DSA and LLD problem in MongoDB with all 5 languages.

- dsa_problems:  already have python + javascript  -> add java, cpp, go
- sd_problems:   LLD problems have python + java   -> add javascript, cpp, go
                 HLD problems have no starter_code  -> skip

Parses Python function signatures to generate equivalent code in each target language.
For multi-method / multi-class LLD problems, translates the full OOP structure.

Usage:
    python -m byo.scripts.enrich_starter_code
    python -m byo.scripts.enrich_starter_code --dry-run
"""

import argparse
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Env setup
# ---------------------------------------------------------------------------
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, "backend", ".env"), override=False)
except ImportError:
    print("WARN: python-dotenv not installed, relying on shell env")


# ═══════════════════════════════════════════════════════════════════════════
# Type mapping tables
# ═══════════════════════════════════════════════════════════════════════════

def _parse_python_type(raw: str) -> dict:
    """
    Parse a Python type annotation into a structured dict.
    Examples:
        "int"                -> {"base": "int"}
        "List[int]"          -> {"base": "List", "inner": [{"base": "int"}]}
        "List[List[int]]"    -> {"base": "List", "inner": [{"base": "List", "inner": [{"base": "int"}]}]}
        "Optional[ListNode]" -> {"base": "Optional", "inner": [{"base": "ListNode"}]}
        "'Optional[Node]'"   -> {"base": "Optional", "inner": [{"base": "Node"}]}
        "'TreeNode'"         -> {"base": "TreeNode"}
    """
    raw = raw.strip().strip("'\"")

    # Match generic like List[...], Optional[...]
    m = re.match(r'^(\w+)\[(.+)\]$', raw)
    if m:
        outer = m.group(1)
        inner_raw = m.group(2)
        # Split inner args at top-level commas (for Dict[K, V] etc.)
        inner_parts = _split_type_args(inner_raw)
        return {"base": outer, "inner": [_parse_python_type(p) for p in inner_parts]}
    return {"base": raw.strip()}


def _split_type_args(s: str) -> List[str]:
    """Split 'int, List[int]' respecting brackets."""
    parts = []
    depth = 0
    current = ""
    for ch in s:
        if ch == '[':
            depth += 1
            current += ch
        elif ch == ']':
            depth -= 1
            current += ch
        elif ch == ',' and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


# ---------------------------------------------------------------------------
# Java type conversion
# ---------------------------------------------------------------------------
def _to_java_type(t: dict) -> str:
    base = t["base"]
    inner = t.get("inner", [])

    if base == "List" and len(inner) == 1:
        inner_t = inner[0]
        # List[int] -> int[], List[List[int]] -> int[][]
        if inner_t["base"] == "List":
            return _to_java_type(inner_t) + "[]"
        java_inner = _to_java_type(inner_t)
        return java_inner + "[]"
    if base == "Optional" and len(inner) == 1:
        return _to_java_type(inner[0])
    if base == "Dict" and len(inner) == 2:
        k = _to_java_boxed(inner[0])
        v = _to_java_boxed(inner[1])
        return f"Map<{k}, {v}>"
    if base == "Set" and len(inner) == 1:
        return f"Set<{_to_java_boxed(inner[0])}>"
    if base == "Tuple" and inner:
        # No direct Java equivalent; use int[] for Tuple[int, ...]
        return "int[]"

    # Primitives and known types
    mapping = {
        "int": "int",
        "float": "double",
        "str": "String",
        "bool": "boolean",
        "None": "void",
        "void": "void",
        "TreeNode": "TreeNode",
        "ListNode": "ListNode",
        "Node": "Node",
    }
    return mapping.get(base, base)


def _to_java_boxed(t: dict) -> str:
    """Java boxed type for generics."""
    s = _to_java_type(t)
    boxed = {"int": "Integer", "double": "Double", "boolean": "Boolean", "float": "Float"}
    return boxed.get(s, s)


# ---------------------------------------------------------------------------
# C++ type conversion
# ---------------------------------------------------------------------------
def _to_cpp_type(t: dict) -> str:
    base = t["base"]
    inner = t.get("inner", [])

    if base == "List" and len(inner) == 1:
        cpp_inner = _to_cpp_type(inner[0])
        return f"vector<{cpp_inner}>"
    if base == "Optional" and len(inner) == 1:
        inner_cpp = _to_cpp_type(inner[0])
        # Avoid double-pointer: TreeNode* is already a pointer
        if inner_cpp.endswith("*"):
            return inner_cpp
        return inner_cpp + "*"
    if base == "Dict" and len(inner) == 2:
        k = _to_cpp_type(inner[0])
        v = _to_cpp_type(inner[1])
        return f"unordered_map<{k}, {v}>"
    if base == "Set" and len(inner) == 1:
        return f"unordered_set<{_to_cpp_type(inner[0])}>"
    if base == "Tuple" and inner:
        parts = ", ".join(_to_cpp_type(i) for i in inner)
        return f"tuple<{parts}>"

    mapping = {
        "int": "int",
        "float": "double",
        "str": "string",
        "bool": "bool",
        "None": "void",
        "void": "void",
        "TreeNode": "TreeNode*",
        "ListNode": "ListNode*",
        "Node": "Node*",
    }
    return mapping.get(base, base)


def _cpp_needs_ref(t: dict) -> bool:
    """Whether a C++ param should be passed by reference."""
    base = t["base"]
    if base in ("List", "Dict", "Set"):
        return True
    if base == "str":
        return True
    return False


# ---------------------------------------------------------------------------
# Go type conversion
# ---------------------------------------------------------------------------
def _to_go_type(t: dict) -> str:
    base = t["base"]
    inner = t.get("inner", [])

    if base == "List" and len(inner) == 1:
        go_inner = _to_go_type(inner[0])
        return f"[]{go_inner}"
    if base == "Optional" and len(inner) == 1:
        inner_go = _to_go_type(inner[0])
        if inner_go.startswith("*"):
            return inner_go
        return f"*{inner_go}"
    if base == "Dict" and len(inner) == 2:
        k = _to_go_type(inner[0])
        v = _to_go_type(inner[1])
        return f"map[{k}]{v}"
    if base == "Set" and len(inner) == 1:
        k = _to_go_type(inner[0])
        return f"map[{k}]bool"
    if base == "Tuple" and inner:
        return "[]int"

    mapping = {
        "int": "int",
        "float": "float64",
        "str": "string",
        "bool": "bool",
        "None": "",
        "void": "",
        "TreeNode": "*TreeNode",
        "ListNode": "*ListNode",
        "Node": "*Node",
    }
    return mapping.get(base, base)


# ═══════════════════════════════════════════════════════════════════════════
# Python signature parser
# ═══════════════════════════════════════════════════════════════════════════

# Matches:  def methodName(self, param1: Type1, param2: Type2) -> ReturnType:
_METHOD_RE = re.compile(
    r'def\s+(\w+)\s*\(\s*self\s*'
    r'(?:,\s*(.*?))?\s*\)'
    r'(?:\s*->\s*(.+?))?\s*:'
)

# Matches:  class ClassName:  or  class ClassName(Base):
_CLASS_RE = re.compile(r'class\s+(\w+)(?:\s*\(.*?\))?\s*:')


def _parse_params(params_str: str) -> List[Tuple[str, dict]]:
    """Parse 'param1: Type1, param2: Type2' into [(name, parsed_type), ...]"""
    if not params_str or not params_str.strip():
        return []
    result = []
    # Split on commas respecting brackets
    parts = _split_type_args(params_str)
    for part in parts:
        part = part.strip()
        if ':' in part:
            name, type_str = part.split(':', 1)
            result.append((name.strip(), _parse_python_type(type_str.strip())))
        else:
            # No type annotation -- treat as generic
            result.append((part.strip(), {"base": "Object"}))
    return result


def _parse_return_type(ret_str: Optional[str]) -> dict:
    """Parse return type string, defaulting to void."""
    if not ret_str or ret_str.strip().lower() == 'none':
        return {"base": "None"}
    return _parse_python_type(ret_str.strip())


def _to_camel_case(snake: str) -> str:
    """Convert snake_case to camelCase (for Go public exports, use PascalCase)."""
    parts = snake.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def _to_pascal_case(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return ''.join(p.capitalize() for p in snake.split('_'))


# ═══════════════════════════════════════════════════════════════════════════
# DSA code generators (single class Solution with methods)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_dsa_methods(python_code: str) -> List[dict]:
    """
    Extract class name and methods from Python DSA starter code.
    Returns list of {class_name, method_name, params: [(name, parsed_type)], return_type}.
    Handles multi-method classes (MinStack, LRUCache, etc.).
    """
    methods = []
    current_class = "Solution"
    for line in python_code.split('\n'):
        cls_m = _CLASS_RE.search(line)
        if cls_m:
            current_class = cls_m.group(1)

        meth_m = _METHOD_RE.search(line)
        if meth_m:
            method_name = meth_m.group(1)
            params_str = meth_m.group(2)
            ret_str = meth_m.group(3)
            params = _parse_params(params_str)
            ret_type = _parse_return_type(ret_str)
            methods.append({
                "class_name": current_class,
                "method_name": method_name,
                "params": params,
                "return_type": ret_type,
            })
    return methods


def _group_methods_by_class(methods: List[dict]) -> Dict[str, List[dict]]:
    """Group methods by class name, preserving order."""
    groups: Dict[str, List[dict]] = {}
    for m in methods:
        cls = m["class_name"]
        if cls not in groups:
            groups[cls] = []
        groups[cls].append(m)
    return groups


# --- Java generator ---
def _gen_java_dsa(methods: List[dict]) -> str:
    groups = _group_methods_by_class(methods)
    parts = []
    for cls_name, cls_methods in groups.items():
        lines = [f"class {cls_name} {{"]
        for m in cls_methods:
            mname = m["method_name"]
            if mname == "__init__":
                # Constructor
                params_str = ", ".join(
                    f"{_to_java_type(pt)} {pn}" for pn, pt in m["params"]
                )
                lines.append(f"    public {cls_name}({params_str}) {{")
                lines.append(f"    }}")
            else:
                ret_java = _to_java_type(m["return_type"])
                params_str = ", ".join(
                    f"{_to_java_type(pt)} {pn}" for pn, pt in m["params"]
                )
                default_return = _java_default_return(ret_java)
                lines.append(f"    public {ret_java} {mname}({params_str}) {{")
                if default_return:
                    lines.append(f"        {default_return}")
                lines.append(f"    }}")
        lines.append("}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _java_default_return(java_type: str) -> str:
    if java_type == "void":
        return ""
    if java_type == "int":
        return "return 0;"
    if java_type == "double":
        return "return 0.0;"
    if java_type == "boolean":
        return "return false;"
    if java_type == "String":
        return 'return "";'
    if java_type == "float":
        return "return 0.0f;"
    return "return null;"


# --- C++ generator ---
def _gen_cpp_dsa(methods: List[dict]) -> str:
    groups = _group_methods_by_class(methods)
    parts = []
    for cls_name, cls_methods in groups.items():
        lines = [f"class {cls_name} {{", "public:"]
        for m in cls_methods:
            mname = m["method_name"]
            if mname == "__init__":
                # Constructor
                params_str = ", ".join(
                    f"{_to_cpp_type(pt)} {pn}" for pn, pt in m["params"]
                )
                lines.append(f"    {cls_name}({params_str}) {{")
                lines.append(f"    }}")
            else:
                ret_cpp = _to_cpp_type(m["return_type"])
                params_parts = []
                for pn, pt in m["params"]:
                    cpp_t = _to_cpp_type(pt)
                    if _cpp_needs_ref(pt):
                        params_parts.append(f"{cpp_t}& {pn}")
                    else:
                        params_parts.append(f"{cpp_t} {pn}")
                params_str = ", ".join(params_parts)
                default_return = _cpp_default_return(ret_cpp)
                lines.append(f"    {ret_cpp} {mname}({params_str}) {{")
                if default_return:
                    lines.append(f"        {default_return}")
                lines.append(f"    }}")
        lines.append("};")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _cpp_default_return(cpp_type: str) -> str:
    if cpp_type == "void":
        return ""
    if cpp_type in ("int", "double", "float"):
        return "return 0;"
    if cpp_type == "bool":
        return "return false;"
    if cpp_type == "string":
        return 'return "";'
    if cpp_type.endswith("*"):
        return "return nullptr;"
    return "return {};";


# --- Go generator ---
def _gen_go_dsa(methods: List[dict]) -> str:
    groups = _group_methods_by_class(methods)
    parts = []
    for cls_name, cls_methods in groups.items():
        # Check if it's a design class (has constructor)
        has_constructor = any(m["method_name"] == "__init__" for m in cls_methods)

        if has_constructor:
            # Emit a struct + Constructor + methods
            lines = [f"type {cls_name} struct {{", "}}", ""]
            for m in cls_methods:
                mname = m["method_name"]
                if mname == "__init__":
                    params_str = ", ".join(
                        f"{pn} {_to_go_type(pt)}" for pn, pt in m["params"]
                    )
                    lines.append(f"func Constructor({params_str}) {cls_name} {{")
                    lines.append(f"    return {cls_name}{{}}")
                    lines.append("}")
                else:
                    go_name = _to_pascal_case(mname) if '_' in mname else (mname[0].upper() + mname[1:])
                    ret_go = _to_go_type(m["return_type"])
                    params_str = ", ".join(
                        f"{pn} {_to_go_type(pt)}" for pn, pt in m["params"]
                    )
                    ret_part = f" {ret_go}" if ret_go else ""
                    default_return = _go_default_return(ret_go)
                    lines.append(f"func (this *{cls_name}) {go_name}({params_str}){ret_part} {{")
                    if default_return:
                        lines.append(f"    {default_return}")
                    lines.append("}")
                lines.append("")
            parts.append("\n".join(lines).rstrip())
        else:
            # Simple Solution class -- emit standalone functions
            for m in cls_methods:
                mname = m["method_name"]
                ret_go = _to_go_type(m["return_type"])
                params_str = ", ".join(
                    f"{pn} {_to_go_type(pt)}" for pn, pt in m["params"]
                )
                ret_part = f" {ret_go}" if ret_go else ""
                default_return = _go_default_return(ret_go)
                lines = [f"func {mname}({params_str}){ret_part} {{"]
                if default_return:
                    lines.append(f"    {default_return}")
                lines.append("}")
                parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _go_default_return(go_type: str) -> str:
    if not go_type:
        return ""
    if go_type in ("int", "int64", "float64"):
        return "return 0"
    if go_type == "bool":
        return "return false"
    if go_type == "string":
        return 'return ""'
    if go_type.startswith("*"):
        return "return nil"
    if go_type.startswith("[]") or go_type.startswith("map["):
        return "return nil"
    return "return *new(" + go_type + ")"


# ═══════════════════════════════════════════════════════════════════════════
# LLD code generators (multi-class OOP translation)
# ═══════════════════════════════════════════════════════════════════════════

def _gen_lld_javascript(python_code: str) -> str:
    """
    Translate Python LLD starter code to JavaScript (ES6 class syntax).
    Handles enums, classes, abstract classes, constructors, methods.
    """
    lines_out = []  # type: List[str]
    lines = python_code.split('\n')
    i = 0
    in_class = False
    class_name = ""
    indent_base = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip import lines
        if stripped.startswith(('from ', 'import ')):
            i += 1
            continue

        # Blank lines
        if not stripped:
            lines_out.append("")
            i += 1
            continue

        # Enum class
        enum_m = re.match(r'class\s+(\w+)\s*\(Enum\)\s*:', stripped)
        if enum_m:
            ename = enum_m.group(1)
            lines_out.append(f"const {ename} = Object.freeze({{")
            i += 1
            while i < len(lines):
                estrip = lines[i].strip()
                if not estrip:
                    i += 1
                    continue
                m2 = re.match(r'(\w+)\s*=\s*(.+)', estrip)
                if m2:
                    lines_out.append(f"    {m2.group(1)}: {m2.group(2)},")
                    i += 1
                    continue
                break
            lines_out.append("});")
            lines_out.append("")
            continue

        # ABC class
        abc_m = re.match(r'class\s+(\w+)\s*\(ABC\)\s*:', stripped)
        if abc_m:
            class_name = abc_m.group(1)
            lines_out.append(f"class {class_name} {{")
            in_class = True
            i += 1
            # Process abstract methods
            while i < len(lines):
                raw_line = lines[i]
                ms = raw_line.strip()
                if not ms:
                    i += 1
                    continue
                if ms.startswith('@abstractmethod'):
                    i += 1
                    continue
                meth_m2 = _METHOD_RE.search(ms)
                if meth_m2:
                    mn = meth_m2.group(1)
                    ps = meth_m2.group(2)
                    param_names = [p.split(':')[0].strip() for p in _split_type_args(ps)] if ps else []
                    pstr = ", ".join(param_names)
                    lines_out.append(f"    {mn}({pstr}) {{")
                    lines_out.append(f'        throw new Error("Not implemented");')
                    lines_out.append(f"    }}")
                    # skip body (pass)
                    i += 1
                    while i < len(lines) and lines[i].strip() in ('pass', ''):
                        i += 1
                    continue
                # Non-empty, non-decorator, non-method line: check if still indented
                if not raw_line[0:1] in (' ', '\t'):
                    break  # top-level line = end of class
                i += 1
            lines_out.append("}")
            lines_out.append("")
            in_class = False
            continue

        # Regular class
        cls_m = re.match(r'class\s+(\w+)(?:\s*\((\w+)\))?\s*:', stripped)
        if cls_m:
            class_name = cls_m.group(1)
            parent = cls_m.group(2)
            if parent and parent not in ('ABC', 'Enum', 'object'):
                lines_out.append(f"class {class_name} extends {parent} {{")
            else:
                lines_out.append(f"class {class_name} {{")
            in_class = True
            i += 1

            # Process class body
            while i < len(lines):
                raw_line = lines[i]
                ms = raw_line.strip()
                if not ms:
                    i += 1
                    continue
                # Detect end of class: non-empty line at top level (no indent)
                if not raw_line[0:1] in (' ', '\t'):
                    break
                if ms.startswith('@'):
                    i += 1
                    continue

                meth_m2 = _METHOD_RE.search(ms)
                if meth_m2:
                    mn = meth_m2.group(1)
                    ps = meth_m2.group(2)
                    param_names = [p.split(':')[0].strip() for p in _split_type_args(ps)] if ps else []
                    pstr = ", ".join(param_names)

                    if mn == '__init__':
                        lines_out.append(f"    constructor({pstr}) {{")
                        # Parse body for self.x = x assignments
                        i += 1
                        while i < len(lines):
                            bs = lines[i].strip()
                            if not bs or bs == 'pass':
                                i += 1
                                continue
                            assign_m = re.match(r'self\.(\w+)\s*=\s*(.+)', bs)
                            if assign_m:
                                attr = assign_m.group(1)
                                val = assign_m.group(2).strip()
                                val = _py_val_to_js(val, param_names)
                                lines_out.append(f"        this.{attr} = {val};")
                                i += 1
                                continue
                            # Check if still in method body (deeper indent)
                            if lines[i][0:1] in (' ', '\t') and not re.match(r'\s*(def |class )', lines[i]):
                                i += 1
                                continue
                            break
                        lines_out.append(f"    }}")
                        continue
                    else:
                        lines_out.append(f"    {mn}({pstr}) {{")
                        # skip body (pass or single line)
                        i += 1
                        while i < len(lines):
                            bs = lines[i].strip()
                            if not bs or bs == 'pass':
                                i += 1
                                continue
                            if lines[i][0:1] in (' ', '\t') and not re.match(r'\s*(def |class )', lines[i]):
                                i += 1
                                continue
                            break
                        lines_out.append(f"    }}")
                        continue

                # Non-method indented content (skip)
                i += 1

            lines_out.append("}")
            lines_out.append("")
            in_class = False
            continue

        i += 1

    return "\n".join(lines_out).strip()


def _py_val_to_js(val: str, param_names: List[str]) -> str:
    """Translate a Python value expression to JS."""
    if val in param_names:
        return val
    if val == 'None':
        return 'null'
    if val == 'True':
        return 'true'
    if val == 'False':
        return 'false'
    if val == '[]':
        return '[]'
    if val == '{}':
        return '{}'
    if val.startswith('datetime.now()'):
        return 'new Date()'
    # dict() / list()
    if val == 'dict()':
        return '{}'
    if val == 'list()':
        return '[]'
    if val == 'set()':
        return 'new Set()'
    return val


def _gen_lld_cpp(python_code: str) -> str:
    """
    Translate Python LLD starter code to C++ skeleton.
    """
    lines_out = []  # type: List[str]
    lines = python_code.split('\n')
    i = 0

    # Collect enum names for reference
    enum_names = set()  # type: set
    for line in lines:
        em = re.match(r'\s*class\s+(\w+)\s*\(Enum\)\s*:', line.strip())
        if em:
            enum_names.add(em.group(1))

    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith(('from ', 'import ')):
            i += 1
            continue

        if not stripped:
            lines_out.append("")
            i += 1
            continue

        # Enum
        enum_m = re.match(r'class\s+(\w+)\s*\(Enum\)\s*:', stripped)
        if enum_m:
            ename = enum_m.group(1)
            lines_out.append(f"enum class {ename} {{")
            i += 1
            members = []
            while i < len(lines):
                es = lines[i].strip()
                m2 = re.match(r'(\w+)\s*=\s*\d+', es)
                if m2:
                    members.append(m2.group(1))
                    i += 1
                elif not es:
                    i += 1
                    continue
                else:
                    break
            lines_out.append("    " + ", ".join(members))
            lines_out.append("};")
            lines_out.append("")
            continue

        # ABC
        abc_m = re.match(r'class\s+(\w+)\s*\(ABC\)\s*:', stripped)
        if abc_m:
            cname = abc_m.group(1)
            lines_out.append(f"class {cname} {{")
            lines_out.append("public:")
            i += 1
            while i < len(lines):
                raw_line = lines[i]
                ms = raw_line.strip()
                if not ms or ms.startswith('@'):
                    i += 1
                    continue
                # End of class: non-empty, top-level line
                if not raw_line[0:1] in (' ', '\t'):
                    break
                meth_m = _METHOD_RE.search(ms)
                if meth_m:
                    mn = meth_m.group(1)
                    ps = meth_m.group(2)
                    ret_s = meth_m.group(3)
                    params = _parse_params(ps)
                    ret_t = _parse_return_type(ret_s)
                    cpp_ret = _to_cpp_type(ret_t)
                    cpp_params = ", ".join(
                        f"{'const ' if _cpp_needs_ref(pt) else ''}{_to_cpp_type(pt)}{'& ' if _cpp_needs_ref(pt) else ' '}{pn}"
                        for pn, pt in params
                    )
                    lines_out.append(f"    virtual {cpp_ret} {mn}({cpp_params}) = 0;")
                    i += 1
                    while i < len(lines) and lines[i].strip() in ('pass', ''):
                        i += 1
                    continue
                i += 1
            lines_out.append(f"    virtual ~{cname}() = default;")
            lines_out.append("};")
            lines_out.append("")
            continue

        # Regular class
        cls_m = re.match(r'class\s+(\w+)(?:\s*\((\w+)\))?\s*:', stripped)
        if cls_m:
            cname = cls_m.group(1)
            parent = cls_m.group(2)
            if parent and parent not in ('ABC', 'Enum', 'object'):
                lines_out.append(f"class {cname} : public {parent} {{")
            else:
                lines_out.append(f"class {cname} {{")
            lines_out.append("public:")
            i += 1

            # Track instance variables for member declaration
            members = []  # type: List[Tuple[str, str]]

            while i < len(lines):
                raw_line = lines[i]
                ms = raw_line.strip()
                if not ms or ms.startswith('@'):
                    i += 1
                    continue
                # End of class: non-empty, top-level line
                if not raw_line[0:1] in (' ', '\t'):
                    break

                meth_m = _METHOD_RE.search(ms)
                if meth_m:
                    mn = meth_m.group(1)
                    ps = meth_m.group(2)
                    ret_s = meth_m.group(3)
                    params = _parse_params(ps)
                    ret_t = _parse_return_type(ret_s)

                    if mn == '__init__':
                        cpp_params = ", ".join(
                            f"{_to_cpp_type(pt)} {pn}" for pn, pt in params
                        )
                        lines_out.append(f"    {cname}({cpp_params}) {{")
                        i += 1
                        while i < len(lines):
                            bs = lines[i].strip()
                            if not bs or bs == 'pass':
                                i += 1
                                continue
                            am = re.match(r'self\.(\w+)\s*=\s*(.+)', bs)
                            if am:
                                attr = am.group(1)
                                val = am.group(2).strip()
                                # Track member
                                cpp_val = _py_val_to_cpp(val, [p[0] for p in params])
                                lines_out.append(f"        this->{attr} = {cpp_val};")
                                i += 1
                                continue
                            if lines[i].startswith((' ', '\t')) and not re.match(r'\s*(def |class )', lines[i]):
                                i += 1
                                continue
                            break
                        lines_out.append(f"    }}")
                        continue
                    else:
                        cpp_ret = _to_cpp_type(ret_t)
                        cpp_params = ", ".join(
                            f"{_to_cpp_type(pt)}{'& ' if _cpp_needs_ref(pt) else ' '}{pn}"
                            for pn, pt in params
                        )
                        default_ret = _cpp_default_return(cpp_ret)
                        lines_out.append(f"    {cpp_ret} {mn}({cpp_params}) {{")
                        if default_ret:
                            lines_out.append(f"        {default_ret}")
                        lines_out.append(f"    }}")
                        i += 1
                        while i < len(lines):
                            bs = lines[i].strip()
                            if not bs or bs == 'pass':
                                i += 1
                                continue
                            if lines[i].startswith((' ', '\t')) and not re.match(r'\s*(def |class )', lines[i]):
                                i += 1
                                continue
                            break
                        continue

                # Non-method indented content (skip)
                i += 1

            lines_out.append("};")
            lines_out.append("")
            continue

        i += 1

    return "\n".join(lines_out).strip()


def _py_val_to_cpp(val: str, param_names: List[str]) -> str:
    if val in param_names:
        return val
    if val == 'None':
        return 'nullptr'
    if val == 'True':
        return 'true'
    if val == 'False':
        return 'false'
    if val == '[]':
        return '{}'
    if val == '{}':
        return '{}'
    if val.startswith('datetime.now()'):
        return 'std::chrono::system_clock::now()'
    return val


def _gen_lld_go(python_code: str) -> str:
    """
    Translate Python LLD starter code to Go skeleton.
    Go uses structs + interfaces instead of classes.
    """
    lines_out = []  # type: List[str]
    lines = python_code.split('\n')
    i = 0

    # First pass: collect enum names, class names, abstract classes
    enum_names = set()  # type: set
    abc_names = set()  # type: set
    class_names = set()  # type: set
    for line in lines:
        s = line.strip()
        em = re.match(r'class\s+(\w+)\s*\(Enum\)\s*:', s)
        if em:
            enum_names.add(em.group(1))
        am = re.match(r'class\s+(\w+)\s*\(ABC\)\s*:', s)
        if am:
            abc_names.add(am.group(1))
        cm = re.match(r'class\s+(\w+)', s)
        if cm:
            class_names.add(cm.group(1))

    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith(('from ', 'import ')):
            i += 1
            continue

        if not stripped:
            lines_out.append("")
            i += 1
            continue

        # Enum -> Go const iota
        enum_m = re.match(r'class\s+(\w+)\s*\(Enum\)\s*:', stripped)
        if enum_m:
            ename = enum_m.group(1)
            lines_out.append(f"type {ename} int")
            lines_out.append("")
            lines_out.append("const (")
            i += 1
            first = True
            while i < len(lines):
                es = lines[i].strip()
                m2 = re.match(r'(\w+)\s*=\s*\d+', es)
                if m2:
                    mname = m2.group(1)
                    if first:
                        lines_out.append(f"    {mname} {ename} = iota + 1")
                        first = False
                    else:
                        lines_out.append(f"    {mname}")
                    i += 1
                elif not es:
                    i += 1
                    continue
                else:
                    break
            lines_out.append(")")
            lines_out.append("")
            continue

        # ABC -> Go interface
        abc_m = re.match(r'class\s+(\w+)\s*\(ABC\)\s*:', stripped)
        if abc_m:
            iname = abc_m.group(1)
            lines_out.append(f"type {iname} interface {{")
            i += 1
            while i < len(lines):
                raw_line = lines[i]
                ms = raw_line.strip()
                if not ms or ms.startswith('@'):
                    i += 1
                    continue
                if not raw_line[0:1] in (' ', '\t'):
                    break  # end of class
                meth_m = _METHOD_RE.search(ms)
                if meth_m:
                    mn = meth_m.group(1)
                    ps = meth_m.group(2)
                    ret_s = meth_m.group(3)
                    params = _parse_params(ps)
                    ret_t = _parse_return_type(ret_s)
                    go_ret = _to_go_type(ret_t)
                    go_params = ", ".join(
                        f"{pn} {_to_go_type(pt)}" for pn, pt in params
                    )
                    go_name = _to_pascal_case(mn) if '_' in mn else (mn[0].upper() + mn[1:])
                    ret_part = f" {go_ret}" if go_ret else ""
                    lines_out.append(f"    {go_name}({go_params}){ret_part}")
                    i += 1
                    while i < len(lines) and lines[i].strip() in ('pass', ''):
                        i += 1
                    continue
                i += 1
            lines_out.append("}")
            lines_out.append("")
            continue

        # Regular class -> Go struct + methods
        cls_m = re.match(r'class\s+(\w+)(?:\s*\((\w+)\))?\s*:', stripped)
        if cls_m:
            cname = cls_m.group(1)
            lines_out.append(f"type {cname} struct {{")
            i += 1

            # Collect fields from __init__
            struct_fields = []  # type: List[Tuple[str, str]]
            saved_methods = []  # type: List[dict]

            while i < len(lines):
                raw_line = lines[i]
                ms = raw_line.strip()
                if not ms or ms.startswith('@'):
                    i += 1
                    continue
                if not raw_line[0:1] in (' ', '\t'):
                    break  # end of class

                meth_m = _METHOD_RE.search(ms)
                if meth_m:
                    mn = meth_m.group(1)
                    ps = meth_m.group(2)
                    ret_s = meth_m.group(3)
                    params = _parse_params(ps)
                    ret_t = _parse_return_type(ret_s)

                    if mn == '__init__':
                        i += 1
                        init_params = params
                        while i < len(lines):
                            bs = lines[i].strip()
                            if not bs or bs == 'pass':
                                i += 1
                                continue
                            am = re.match(r'self\.(\w+)\s*=\s*(.+)', bs)
                            if am:
                                attr = am.group(1)
                                val = am.group(2).strip()
                                # Try to infer type from constructor params or value
                                go_t = _infer_go_field_type(attr, val, init_params)
                                field_name = _to_pascal_case(attr) if '_' in attr else (attr[0].upper() + attr[1:])
                                struct_fields.append((field_name, go_t))
                                i += 1
                                continue
                            if lines[i].startswith((' ', '\t')) and not re.match(r'\s*(def |class )', lines[i]):
                                i += 1
                                continue
                            break
                        saved_methods.append({
                            "name": "__init__",
                            "params": init_params,
                            "return_type": ret_t,
                        })
                    else:
                        saved_methods.append({
                            "name": mn,
                            "params": params,
                            "return_type": ret_t,
                        })
                        i += 1
                        while i < len(lines):
                            bs = lines[i].strip()
                            if not bs or bs == 'pass':
                                i += 1
                                continue
                            if lines[i].startswith((' ', '\t')) and not re.match(r'\s*(def |class )', lines[i]):
                                i += 1
                                continue
                            break
                    continue

                # Non-method indented content (skip)
                i += 1

            # Write struct fields
            if struct_fields:
                for fn, ft in struct_fields:
                    lines_out.append(f"    {fn} {ft}")
            lines_out.append("}")
            lines_out.append("")

            # Write constructor and methods
            for m in saved_methods:
                mn = m["name"]
                if mn == "__init__":
                    go_params = ", ".join(
                        f"{pn} {_to_go_type(pt)}" for pn, pt in m["params"]
                    )
                    lines_out.append(f"func New{cname}({go_params}) *{cname} {{")
                    lines_out.append(f"    return &{cname}{{}}")
                    lines_out.append("}")
                else:
                    go_name = _to_pascal_case(mn) if '_' in mn else (mn[0].upper() + mn[1:])
                    ret_go = _to_go_type(m["return_type"])
                    go_params = ", ".join(
                        f"{pn} {_to_go_type(pt)}" for pn, pt in m["params"]
                    )
                    ret_part = f" {ret_go}" if ret_go else ""
                    default_ret = _go_default_return(ret_go)
                    lines_out.append(f"func (s *{cname}) {go_name}({go_params}){ret_part} {{")
                    if default_ret:
                        lines_out.append(f"    {default_ret}")
                    lines_out.append("}")
                lines_out.append("")

            continue

        i += 1

    return "\n".join(lines_out).strip()


def _infer_go_field_type(attr: str, val: str, params: List[Tuple[str, dict]]) -> str:
    """Infer Go type for a struct field from init assignment."""
    # If assigned from a param, use that param's type
    for pn, pt in params:
        if val == pn:
            return _to_go_type(pt)
    # Infer from literal value
    if val == 'None':
        return "interface{}"
    if val in ('True', 'False'):
        return "bool"
    if val == '[]':
        return "[]interface{}"
    if val == '{}':
        return "map[string]interface{}"
    if val == 'dict()':
        return "map[string]interface{}"
    if val == 'set()':
        return "map[interface{}]bool"
    if val.startswith('datetime.now()'):
        return "time.Time"
    if re.match(r'^\d+$', val):
        return "int"
    if re.match(r'^\d+\.\d+$', val):
        return "float64"
    if val.startswith(("'", '"')):
        return "string"
    return "interface{}"


# ═══════════════════════════════════════════════════════════════════════════
# Main enrichment logic
# ═══════════════════════════════════════════════════════════════════════════

ALL_LANGUAGES = {"python", "javascript", "java", "cpp", "go"}


def enrich_dsa_problem(doc: dict) -> Optional[Dict[str, str]]:
    """
    Given a DSA problem document, return a dict of missing language starter codes.
    Returns None if nothing to add (already has all 5 or can't parse).
    """
    sc = doc.get("starter_code")
    if not sc or not isinstance(sc, dict):
        return None

    existing = set(sc.keys())
    missing = ALL_LANGUAGES - existing
    if not missing:
        return None

    python_code = sc.get("python")
    if not python_code:
        return None

    methods = _extract_dsa_methods(python_code)
    if not methods:
        return None

    result = {}

    if "java" in missing:
        result["java"] = _gen_java_dsa(methods)
    if "cpp" in missing:
        result["cpp"] = _gen_cpp_dsa(methods)
    if "go" in missing:
        result["go"] = _gen_go_dsa(methods)
    if "javascript" in missing:
        # DSA problems should already have JS, but just in case
        result["javascript"] = _gen_js_dsa(methods)

    return result if result else None


def _gen_js_dsa(methods: List[dict]) -> str:
    """Generate JavaScript DSA starter code (function style)."""
    groups = _group_methods_by_class(methods)
    parts = []
    for cls_name, cls_methods in groups.items():
        has_constructor = any(m["method_name"] == "__init__" for m in cls_methods)
        if has_constructor:
            # Design class: Constructor + prototype methods
            for m in cls_methods:
                mn = m["method_name"]
                param_names = [pn for pn, _ in m["params"]]
                pstr = ", ".join(param_names)
                if mn == "__init__":
                    parts.append(f"var {cls_name} = function({pstr}) {{\n    \n}};")
                else:
                    parts.append(f"{cls_name}.prototype.{mn} = function({pstr}) {{\n    \n}};")
        else:
            for m in cls_methods:
                mn = m["method_name"]
                param_names = [pn for pn, _ in m["params"]]
                pstr = ", ".join(param_names)
                parts.append(f"var {mn} = function({pstr}) {{\n    \n}};")
    return "\n".join(parts)


def enrich_lld_problem(doc: dict) -> Optional[Dict[str, str]]:
    """
    Given an LLD problem document, return a dict of missing language starter codes.
    LLD problems have complex multi-class Python code.
    """
    sc = doc.get("starter_code")
    if not sc or not isinstance(sc, dict):
        return None

    existing = set(sc.keys())
    missing = ALL_LANGUAGES - existing
    if not missing:
        return None

    python_code = sc.get("python")
    if not python_code:
        return None

    result = {}

    if "javascript" in missing:
        result["javascript"] = _gen_lld_javascript(python_code)
    if "cpp" in missing:
        result["cpp"] = _gen_lld_cpp(python_code)
    if "go" in missing:
        result["go"] = _gen_lld_go(python_code)
    if "java" in missing:
        # LLD problems should already have Java, but just in case
        # We'd need a full Python->Java LLD translator; skip for now
        pass

    return result if result else None


def main():
    parser = argparse.ArgumentParser(description="Enrich starter_code with all 5 languages")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing")
    parser.add_argument("--uri", type=str, default=None, help="MongoDB URI override")
    args = parser.parse_args()

    import certifi
    from pymongo import MongoClient

    mongo_uri = args.uri or os.environ.get("MONGODB_URI")
    if not mongo_uri:
        print("ERROR: No MONGODB_URI found in env or --uri flag")
        sys.exit(1)

    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    db = client[os.environ.get("MONGODB_DB", "capacity")]

    total_updated = 0
    total_languages_added = 0

    # -----------------------------------------------------------------------
    # 1. DSA problems
    # -----------------------------------------------------------------------
    col_dsa = db["dsa_problems"]
    dsa_problems = list(col_dsa.find({"starter_code": {"$exists": True}}))
    print(f"\n=== DSA Problems ({len(dsa_problems)} with starter_code) ===\n")

    dsa_updated = 0
    dsa_langs_added = 0

    for doc in dsa_problems:
        name = doc.get("name", doc.get("slug", "?"))
        sc = doc.get("starter_code", {})
        existing = set(sc.keys()) & ALL_LANGUAGES
        missing = ALL_LANGUAGES - existing

        if not missing:
            print(f"  [SKIP] {name} -- already has all 5 languages")
            continue

        new_code = enrich_dsa_problem(doc)
        if not new_code:
            print(f"  [WARN] {name} -- could not parse Python signature")
            continue

        lang_names = sorted(new_code.keys())
        print(f"  [ADD]  {name} -- adding {', '.join(lang_names)}")

        if not args.dry_run:
            set_fields = {f"starter_code.{lang}": code for lang, code in new_code.items()}
            col_dsa.update_one({"_id": doc["_id"]}, {"$set": set_fields})

        dsa_updated += 1
        dsa_langs_added += len(new_code)

    print(f"\n  DSA: {dsa_updated} problems updated, {dsa_langs_added} languages added")
    total_updated += dsa_updated
    total_languages_added += dsa_langs_added

    # -----------------------------------------------------------------------
    # 2. SD/LLD problems
    # -----------------------------------------------------------------------
    col_sd = db["sd_problems"]

    # Only LLD problems have starter_code
    lld_problems = list(col_sd.find({
        "starter_code": {"$exists": True},
        "type": "lld",
    }))
    print(f"\n=== LLD Problems ({len(lld_problems)} with starter_code) ===\n")

    lld_updated = 0
    lld_langs_added = 0

    for doc in lld_problems:
        name = doc.get("name", doc.get("slug", "?"))
        sc = doc.get("starter_code", {})
        existing = set(sc.keys()) & ALL_LANGUAGES
        missing = ALL_LANGUAGES - existing

        if not missing:
            print(f"  [SKIP] {name} -- already has all 5 languages")
            continue

        new_code = enrich_lld_problem(doc)
        if not new_code:
            print(f"  [WARN] {name} -- could not generate missing languages")
            continue

        lang_names = sorted(new_code.keys())
        print(f"  [ADD]  {name} -- adding {', '.join(lang_names)}")

        if not args.dry_run:
            set_fields = {f"starter_code.{lang}": code for lang, code in new_code.items()}
            col_sd.update_one({"_id": doc["_id"]}, {"$set": set_fields})

        lld_updated += 1
        lld_langs_added += len(new_code)

    print(f"\n  LLD: {lld_updated} problems updated, {lld_langs_added} languages added")
    total_updated += lld_updated
    total_languages_added += lld_langs_added

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"TOTAL: {total_updated} problems updated, {total_languages_added} languages added")
    if args.dry_run:
        print("  (DRY RUN -- no changes written)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
