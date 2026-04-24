"""Code execution via Judge0 — run/submit for DSA problems.

Test cases from MongoDB have structured inputs ({input: {nums: [1,2], target: 3}, expected: [0,1]}).
Judge0 expects flat stdin/stdout strings. This module wraps the student's code with a test harness
that deserializes the input, calls the function, and prints the output for Judge0 comparison.
"""

import json
import logging
import re
from fastapi import APIRouter, Request
from app.api.routes.auth import get_optional_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/judge", tags=["judge"])


_LEETCODE_PREAMBLE = """\
import sys, json, math, heapq, bisect, itertools, functools, string, re
from typing import List, Optional, Dict, Set, Tuple, Any
from collections import defaultdict, Counter, deque, OrderedDict
from functools import lru_cache, reduce
from itertools import accumulate, combinations, permutations, product
from math import inf, ceil, floor, log2, sqrt, gcd
from heapq import heappush, heappop, heapify

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val; self.left = left; self.right = right

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val; self.next = next
"""


def _build_python_wrapper(student_code: str, tc_input: dict | str, tc_expected) -> tuple[str, str, str]:
    """Build a self-contained Python script that runs the student's code against one test case.

    Returns (full_code, stdin_str, expected_str).
    Judge0 runs full_code with stdin_str piped in, compares stdout to expected_str.
    """
    has_class = bool(re.search(r'class\s+\w+', student_code))

    if isinstance(tc_input, dict):
        if has_class:
            method_match = re.search(r'def\s+(\w+)\s*\(\s*self', student_code)
            method_name = method_match.group(1) if method_match else 'solve'
            runner = f"""{_LEETCODE_PREAMBLE}
{student_code}

_input = json.loads(sys.stdin.read())
_sol = Solution()
_result = _sol.{method_name}(**_input) if isinstance(_input, dict) else _sol.{method_name}(_input)
print(json.dumps(_result))
"""
        else:
            func_match = re.search(r'def\s+(\w+)\s*\(', student_code)
            func_name = func_match.group(1) if func_match else 'solve'
            runner = f"""{_LEETCODE_PREAMBLE}
{student_code}

_input = json.loads(sys.stdin.read())
_result = {func_name}(**_input) if isinstance(_input, dict) else {func_name}(_input)
print(json.dumps(_result))
"""
        stdin_str = json.dumps(tc_input)
    else:
        stdin_str = str(tc_input)
        runner = student_code

    expected_str = _normalize_expected(tc_expected)
    return runner.strip(), stdin_str, expected_str


def _normalize_expected(tc_expected) -> str:
    if isinstance(tc_expected, bool):
        return "true" if tc_expected else "false"
    if isinstance(tc_expected, (list, dict)):
        return json.dumps(tc_expected, separators=(',', ':'))
    return str(tc_expected).strip()


def _build_js_wrapper(student_code: str, tc_input: dict | str, tc_expected) -> tuple[str, str, str]:
    """Build a Node.js script that runs the student's JS code against one test case."""
    if isinstance(tc_input, dict):
        func_match = re.search(r'var\s+(\w+)\s*=\s*function\s*\(([^)]*)\)', student_code)
        if not func_match:
            func_match = re.search(r'function\s+(\w+)\s*\(([^)]*)\)', student_code)
        func_name = func_match.group(1) if func_match else 'solve'
        params_str = func_match.group(2) if func_match else ''
        params = [p.strip() for p in params_str.split(',') if p.strip()]

        args_call = ', '.join(f'_input["{p}"]' for p in params) if params else '...(Object.values(_input))'

        runner = f"""{student_code}

const _input = JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8'));
const _result = {func_name}({args_call});
console.log(JSON.stringify(_result));
"""
        stdin_str = json.dumps(tc_input)
    else:
        stdin_str = str(tc_input)
        runner = student_code

    return runner.strip(), json.dumps(tc_input) if isinstance(tc_input, dict) else str(tc_input), _normalize_expected(tc_expected)


# ── Java type mappings ────────────────────────────────────────────────
_JAVA_TYPE_MAP = {
    "int":          ("int",       "Integer.parseInt({src})",                  False),
    "long":         ("long",      "Long.parseLong({src})",                    False),
    "double":       ("double",    "Double.parseDouble({src})",                False),
    "float":        ("float",     "Float.parseFloat({src})",                  False),
    "boolean":      ("boolean",   "{src}.equals(\"true\")",                   False),
    "char":         ("char",      "{src}.charAt(0)",                          False),
    "String":       ("String",    "{src}",                                    False),
    "int[]":        ("int[]",     "toIntArray(toList({src}))",                True),
    "long[]":       ("long[]",    "toLongArray(toList({src}))",               True),
    "double[]":     ("double[]",  "toDoubleArray(toList({src}))",             True),
    "char[]":       ("char[]",    "toCharArray(toList({src}))",               True),
    "String[]":     ("String[]",  "toStringArray(toList({src}))",             True),
    "int[][]":      ("int[][]",   "toInt2D(toList({src}))",                   True),
    "String[][]":   ("String[][]","toString2D(toList({src}))",                True),
    "List<Integer>":           ("List<Integer>",          "toIntegerList(toList({src}))",              True),
    "List<String>":            ("List<String>",           "toStringList(toList({src}))",               True),
    "List<List<Integer>>":     ("List<List<Integer>>",    "toIntegerList2D(toList({src}))",            True),
    "List<List<String>>":      ("List<List<String>>",     "toStringList2D(toList({src}))",             True),
}


_JAVA_MINI_JSON = r'''
    // ── minimal JSON helpers (stdlib only) ──────────────────────────
    static String readAll() throws Exception {
        StringBuilder sb = new StringBuilder();
        try (java.io.BufferedReader br = new java.io.BufferedReader(
                new java.io.InputStreamReader(System.in))) {
            String line;
            while ((line = br.readLine()) != null) sb.append(line);
        }
        return sb.toString().trim();
    }

    /** Return map of key→raw-JSON-value from a flat JSON object string. */
    static java.util.LinkedHashMap<String, String> parseObject(String s) {
        java.util.LinkedHashMap<String, String> map = new java.util.LinkedHashMap<>();
        s = s.trim();
        if (s.startsWith("{")) s = s.substring(1);
        if (s.endsWith("}"))   s = s.substring(0, s.length() - 1);
        int i = 0;
        while (i < s.length()) {
            // skip whitespace / commas
            while (i < s.length() && (s.charAt(i) == ',' || s.charAt(i) == ' '
                    || s.charAt(i) == '\n' || s.charAt(i) == '\r' || s.charAt(i) == '\t')) i++;
            if (i >= s.length()) break;
            // key
            if (s.charAt(i) != '"') { i++; continue; }
            int ks = ++i;
            while (i < s.length() && s.charAt(i) != '"') { if (s.charAt(i) == '\\') i++; i++; }
            String key = s.substring(ks, i); i++; // closing quote
            // colon
            while (i < s.length() && s.charAt(i) != ':') i++;
            i++; // skip colon
            while (i < s.length() && s.charAt(i) == ' ') i++;
            // value — consume one JSON value
            String val = consumeValue(s, i);
            i += val.length();
            // trim whitespace we consumed
            map.put(key, val.trim());
        }
        return map;
    }

    /** Consume one JSON value starting at position i, return the raw substring. */
    static String consumeValue(String s, int start) {
        int i = start;
        while (i < s.length() && s.charAt(i) == ' ') i++;
        if (i >= s.length()) return "";
        char c = s.charAt(i);
        if (c == '"') {
            int j = i + 1;
            while (j < s.length()) { if (s.charAt(j) == '\\') { j += 2; continue; } if (s.charAt(j) == '"') break; j++; }
            return s.substring(start, j + 1);
        }
        if (c == '[' || c == '{') {
            char open = c, close = (c == '[') ? ']' : '}';
            int depth = 1, j = i + 1;
            boolean inStr = false;
            while (j < s.length() && depth > 0) {
                char ch = s.charAt(j);
                if (inStr) { if (ch == '\\') j++; else if (ch == '"') inStr = false; }
                else { if (ch == '"') inStr = true; else if (ch == open) depth++; else if (ch == close) depth--; }
                j++;
            }
            return s.substring(start, j);
        }
        // number, bool, null
        int j = i;
        while (j < s.length() && s.charAt(j) != ',' && s.charAt(j) != '}' && s.charAt(j) != ']'
                && s.charAt(j) != ' ' && s.charAt(j) != '\n') j++;
        return s.substring(start, j);
    }

    /** Split a JSON array string into its top-level element strings. */
    static java.util.List<String> toList(String s) {
        java.util.List<String> out = new java.util.ArrayList<>();
        s = s.trim();
        if (s.startsWith("[")) s = s.substring(1);
        if (s.endsWith("]"))   s = s.substring(0, s.length() - 1);
        int i = 0;
        while (i < s.length()) {
            while (i < s.length() && (s.charAt(i) == ',' || s.charAt(i) == ' '
                    || s.charAt(i) == '\n' || s.charAt(i) == '\r' || s.charAt(i) == '\t')) i++;
            if (i >= s.length()) break;
            String val = consumeValue(s, i);
            if (!val.trim().isEmpty()) out.add(val.trim());
            i += val.length();
        }
        return out;
    }

    // ── array / list converters ─────────────────────────────────────
    static int[] toIntArray(java.util.List<String> elems) {
        int[] a = new int[elems.size()];
        for (int i = 0; i < elems.size(); i++) a[i] = Integer.parseInt(elems.get(i).trim());
        return a;
    }
    static long[] toLongArray(java.util.List<String> elems) {
        long[] a = new long[elems.size()];
        for (int i = 0; i < elems.size(); i++) a[i] = Long.parseLong(elems.get(i).trim());
        return a;
    }
    static double[] toDoubleArray(java.util.List<String> elems) {
        double[] a = new double[elems.size()];
        for (int i = 0; i < elems.size(); i++) a[i] = Double.parseDouble(elems.get(i).trim());
        return a;
    }
    static char[] toCharArray(java.util.List<String> elems) {
        char[] a = new char[elems.size()];
        for (int i = 0; i < elems.size(); i++) {
            String e = elems.get(i).trim();
            if (e.startsWith("\"")) e = e.substring(1, e.length() - 1);
            a[i] = e.charAt(0);
        }
        return a;
    }
    static String[] toStringArray(java.util.List<String> elems) {
        String[] a = new String[elems.size()];
        for (int i = 0; i < elems.size(); i++) {
            String e = elems.get(i).trim();
            if (e.startsWith("\"")) e = e.substring(1, e.length() - 1);
            a[i] = e;
        }
        return a;
    }
    static java.util.List<Integer> toIntegerList(java.util.List<String> elems) {
        java.util.List<Integer> out = new java.util.ArrayList<>();
        for (String e : elems) out.add(Integer.parseInt(e.trim()));
        return out;
    }
    static java.util.List<String> toStringList(java.util.List<String> elems) {
        java.util.List<String> out = new java.util.ArrayList<>();
        for (String e : elems) {
            e = e.trim();
            if (e.startsWith("\"")) e = e.substring(1, e.length() - 1);
            out.add(e);
        }
        return out;
    }
    static int[][] toInt2D(java.util.List<String> elems) {
        int[][] a = new int[elems.size()][];
        for (int i = 0; i < elems.size(); i++) a[i] = toIntArray(toList(elems.get(i)));
        return a;
    }
    static String[][] toString2D(java.util.List<String> elems) {
        String[][] a = new String[elems.size()][];
        for (int i = 0; i < elems.size(); i++) a[i] = toStringArray(toList(elems.get(i)));
        return a;
    }
    static java.util.List<java.util.List<Integer>> toIntegerList2D(java.util.List<String> elems) {
        java.util.List<java.util.List<Integer>> out = new java.util.ArrayList<>();
        for (String e : elems) out.add(toIntegerList(toList(e)));
        return out;
    }
    static java.util.List<java.util.List<String>> toStringList2D(java.util.List<String> elems) {
        java.util.List<java.util.List<String>> out = new java.util.ArrayList<>();
        for (String e : elems) out.add(toStringList(toList(e)));
        return out;
    }

    // ── result serialisation ────────────────────────────────────────
    static String toJson(Object o) {
        if (o == null) return "null";
        if (o instanceof Boolean) return o.toString();
        if (o instanceof Number)  return o.toString();
        if (o instanceof String)  return "\"" + o + "\"";
        if (o instanceof int[])   { int[] a = (int[])o; StringBuilder sb = new StringBuilder("["); for (int i=0;i<a.length;i++){if(i>0)sb.append(",");sb.append(a[i]);} sb.append("]"); return sb.toString(); }
        if (o instanceof long[])  { long[] a = (long[])o; StringBuilder sb = new StringBuilder("["); for (int i=0;i<a.length;i++){if(i>0)sb.append(",");sb.append(a[i]);} sb.append("]"); return sb.toString(); }
        if (o instanceof double[]){ double[] a = (double[])o; StringBuilder sb = new StringBuilder("["); for (int i=0;i<a.length;i++){if(i>0)sb.append(",");sb.append(a[i]);} sb.append("]"); return sb.toString(); }
        if (o instanceof char[])  { char[] a = (char[])o; StringBuilder sb = new StringBuilder("["); for (int i=0;i<a.length;i++){if(i>0)sb.append(",");sb.append("\"").append(a[i]).append("\"");} sb.append("]"); return sb.toString(); }
        if (o instanceof boolean[]){ boolean[] a = (boolean[])o; StringBuilder sb = new StringBuilder("["); for (int i=0;i<a.length;i++){if(i>0)sb.append(",");sb.append(a[i]);} sb.append("]"); return sb.toString(); }
        if (o instanceof String[]){ String[] a = (String[])o; StringBuilder sb = new StringBuilder("["); for (int i=0;i<a.length;i++){if(i>0)sb.append(",");sb.append("\"").append(a[i]).append("\"");} sb.append("]"); return sb.toString(); }
        if (o instanceof int[][]) { int[][] a = (int[][])o; StringBuilder sb = new StringBuilder("["); for (int i=0;i<a.length;i++){if(i>0)sb.append(",");sb.append(toJson(a[i]));} sb.append("]"); return sb.toString(); }
        if (o instanceof String[][]){ String[][] a = (String[][])o; StringBuilder sb = new StringBuilder("["); for (int i=0;i<a.length;i++){if(i>0)sb.append(",");sb.append(toJson(a[i]));} sb.append("]"); return sb.toString(); }
        if (o instanceof java.util.List) {
            java.util.List<?> list = (java.util.List<?>)o;
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < list.size(); i++) { if (i > 0) sb.append(","); sb.append(toJson(list.get(i))); }
            sb.append("]"); return sb.toString();
        }
        return "\"" + o.toString() + "\"";
    }
'''


def _build_java_wrapper(student_code: str, tc_input: dict | str, tc_expected) -> tuple[str, str, str]:
    """Build a self-contained Java source that runs the student's code against one test case.

    Returns (full_java_code, stdin_str, expected_str).
    The student code must contain `class Solution { ... }` with exactly one public method.
    We generate a *non-public* Main class with a `public static void main` that:
      1. reads JSON from stdin
      2. deserialises into the correct Java types
      3. instantiates Solution and calls the method
      4. prints the result as JSON to stdout
    """

    # ── 1. extract method signature from student code ────────────────
    # Matches: public <return_type> <name>(<params>) {
    sig_re = re.compile(
        r'public\s+'
        r'([\w<>\[\], ]+?)\s+'     # return type (handles generics, arrays)
        r'(\w+)\s*'                 # method name
        r'\(([^)]*)\)',             # params
    )
    m = sig_re.search(student_code)
    if not m:
        raise ValueError("Could not parse Java method signature from student code")

    return_type = m.group(1).strip()
    method_name = m.group(2).strip()
    raw_params  = m.group(3).strip()

    # parse individual params  e.g. "int[] nums, int target"
    params: list[tuple[str, str]] = []  # (type, name)
    if raw_params:
        for part in raw_params.split(","):
            part = part.strip()
            # handle types with generics/arrays: split on last whitespace
            idx = part.rfind(" ")
            if idx == -1:
                continue
            ptype = part[:idx].strip()
            pname = part[idx + 1:].strip()
            params.append((ptype, pname))

    # ── 2. build deserialization lines for each param ────────────────
    deserialize_lines: list[str] = []
    for ptype, pname in params:
        entry = _JAVA_TYPE_MAP.get(ptype)
        if entry is None:
            # Fallback: treat as String
            entry = ("String", "{src}", False)
        java_type, converter_tpl, _ = entry
        src_expr = f'map.get("{pname}")'
        converter = converter_tpl.replace("{src}", src_expr)
        deserialize_lines.append(f"        {java_type} {pname} = {converter};")

    deserialize_block = "\n".join(deserialize_lines)

    # ── 3. build the method call ─────────────────────────────────────
    arg_names = ", ".join(pname for _, pname in params)
    if return_type == "void":
        call_block = f"        sol.{method_name}({arg_names});\n        System.out.println(\"null\");"
    else:
        call_block = (
            f"        {return_type} _result = sol.{method_name}({arg_names});\n"
            f"        System.out.println(toJson(_result));"
        )

    # ── 4. assemble full source ──────────────────────────────────────
    full_code = f"""\
import java.util.*;
import java.io.*;

{student_code}

class Main {{
{_JAVA_MINI_JSON}

    public static void main(String[] args) throws Exception {{
        String raw = readAll();
        java.util.LinkedHashMap<String, String> map = parseObject(raw);
        Solution sol = new Solution();
{deserialize_block}
{call_block}
    }}
}}
"""

    # ── 5. stdin / expected ──────────────────────────────────────────
    if isinstance(tc_input, dict):
        stdin_str = json.dumps(tc_input)
    else:
        stdin_str = str(tc_input)

    return full_code.strip(), stdin_str, _normalize_expected(tc_expected)


# ---------------------------------------------------------------------------
#  Go wrapper
# ---------------------------------------------------------------------------

# Match standalone func: func twoSum(nums []int, target int) []int {
_GO_FUNC_RE = re.compile(
    r'func\s+(?P<name>[a-zA-Z_]\w*)\s*\((?P<params>[^)]*)\)\s*(?P<ret>[^{]*)\{'
)


def _go_parse_params(params_str: str) -> list[tuple[str, str]]:
    """Parse a Go parameter list into [(name, type), ...].

    Handles both explicit-per-param ``a int, b int`` and grouped ``a, b int``.
    """
    if not params_str.strip():
        return []

    parts = [p.strip() for p in params_str.split(',') if p.strip()]

    # First pass: split each comma-separated segment into tokens.
    raw: list[list[str]] = []
    for part in parts:
        tokens = part.split()
        raw.append(tokens)

    # Second pass: resolve grouped params.  Walk backwards so that a
    # name-only segment inherits the type from the next segment that has one.
    resolved: list[tuple[str, str]] = []
    last_type = "interface{}"
    for tokens in reversed(raw):
        if len(tokens) >= 2:
            name = tokens[0]
            typ = ' '.join(tokens[1:])
            last_type = typ
        else:
            name = tokens[0]
            typ = last_type
        resolved.append((name, typ))
    resolved.reverse()
    return resolved


def _go_struct_field(name: str, go_type: str) -> str:
    """Return one struct-field line with an exported name + json tag."""
    exported = name[0].upper() + name[1:]
    return f'\t{exported} {go_type} `json:"{name}"`'


def _build_go_wrapper(student_code: str, tc_input: dict | str, tc_expected) -> tuple[str, str, str]:
    """Build a complete Go program wrapping the student's function for Judge0.

    Returns ``(full_go_code, stdin_str, expected_str)``.
    """

    # ── 1. extract the entry-point function signature ───────────────────
    func_match = None
    for m in _GO_FUNC_RE.finditer(student_code):
        if m.group('name') == 'Constructor':
            continue
        func_match = m
        break

    if not func_match:
        # Can't parse -- fall through to raw passthrough.
        return (
            student_code,
            json.dumps(tc_input) if isinstance(tc_input, dict) else str(tc_input),
            _normalize_expected(tc_expected),
        )

    func_name = func_match.group('name')
    params_str = func_match.group('params')
    ret_type = func_match.group('ret').strip()

    params = _go_parse_params(params_str)

    # ── 2. build the input struct ───────────────────────────────────────
    struct_fields = '\n'.join(_go_struct_field(n, t) for n, t in params)
    struct_def = f"type _Input struct {{\n{struct_fields}\n}}"

    # ── 3. build the function call ──────────────────────────────────────
    arg_exprs = [f'inp.{n[0].upper() + n[1:]}' for n, _t in params]
    call_args = ', '.join(arg_exprs)

    if ret_type:
        call_line = f'\tresult := {func_name}({call_args})'
        print_block = (
            '\tresBytes, _ := json.Marshal(result)\n'
            '\tfmt.Println(string(resBytes))'
        )
    else:
        call_line = f'\t{func_name}({call_args})'
        print_block = ''

    # ── 4. TreeNode / ListNode helpers if needed ────────────────────────
    needs_tree = 'TreeNode' in student_code or 'TreeNode' in str(tc_input)
    needs_list = 'ListNode' in student_code or 'ListNode' in str(tc_input)

    helper_structs = ""
    helper_funcs = ""

    if needs_tree:
        helper_structs += """
type TreeNode struct {
\tVal   int
\tLeft  *TreeNode
\tRight *TreeNode
}

"""
        helper_funcs += """
func _buildTree(data []interface{}) *TreeNode {
\tif len(data) == 0 || data[0] == nil {
\t\treturn nil
\t}
\troot := &TreeNode{Val: int(data[0].(float64))}
\tqueue := []*TreeNode{root}
\ti := 1
\tfor len(queue) > 0 && i < len(data) {
\t\tnode := queue[0]
\t\tqueue = queue[1:]
\t\tif i < len(data) && data[i] != nil {
\t\t\tnode.Left = &TreeNode{Val: int(data[i].(float64))}
\t\t\tqueue = append(queue, node.Left)
\t\t}
\t\ti++
\t\tif i < len(data) && data[i] != nil {
\t\t\tnode.Right = &TreeNode{Val: int(data[i].(float64))}
\t\t\tqueue = append(queue, node.Right)
\t\t}
\t\ti++
\t}
\treturn root
}

func _treeToList(root *TreeNode) []interface{} {
\tif root == nil {
\t\treturn []interface{}{}
\t}
\tresult := []interface{}{}
\tqueue := []*TreeNode{root}
\tfor len(queue) > 0 {
\t\tnode := queue[0]
\t\tqueue = queue[1:]
\t\tif node == nil {
\t\t\tresult = append(result, nil)
\t\t} else {
\t\t\tresult = append(result, node.Val)
\t\t\tqueue = append(queue, node.Left, node.Right)
\t\t}
\t}
\tfor len(result) > 0 && result[len(result)-1] == nil {
\t\tresult = result[:len(result)-1]
\t}
\treturn result
}

"""

    if needs_list:
        helper_structs += """
type ListNode struct {
\tVal  int
\tNext *ListNode
}

"""
        helper_funcs += """
func _buildLinkedList(data []interface{}) *ListNode {
\tdummy := &ListNode{}
\tcur := dummy
\tfor _, v := range data {
\t\tcur.Next = &ListNode{Val: int(v.(float64))}
\t\tcur = cur.Next
\t}
\treturn dummy.Next
}

func _linkedListToSlice(head *ListNode) []int {
\tvar result []int
\tfor head != nil {
\t\tresult = append(result, head.Val)
\t\thead = head.Next
\t}
\tif result == nil {
\t\tresult = []int{}
\t}
\treturn result
}

"""

    # ── 5. strip any existing package declaration from student code ─────
    clean_code = re.sub(r'^\s*package\s+\w+\s*', '', student_code).strip()

    # ── 6. assemble the full program ────────────────────────────────────
    full_code = f"""\
package main

import (
\t"encoding/json"
\t"fmt"
\t"io/ioutil"
\t"math"
\t"os"
\t"sort"
\t"strings"
)

// suppress unused-import errors
var _ = math.MaxInt64
var _ = sort.Ints
var _ = strings.Contains

{helper_structs}{helper_funcs}{struct_def}

{clean_code}

func main() {{
\traw, _ := ioutil.ReadAll(os.Stdin)
\tvar inp _Input
\tjson.Unmarshal(raw, &inp)

{call_line}
{print_block}
}}
"""

    # ── 7. stdin / expected ─────────────────────────────────────────────
    if isinstance(tc_input, dict):
        stdin_str = json.dumps(tc_input)
    else:
        stdin_str = str(tc_input)

    return full_code.strip(), stdin_str, _normalize_expected(tc_expected)


# ---------------------------------------------------------------------------
#  C++ wrapper
# ---------------------------------------------------------------------------

# Minimal recursive-descent JSON parser for C++ (stdlib only, no nlohmann).
_CPP_JSON_PARSER = r"""
// ---- minimal JSON parser -------------------------------------------------
struct JVal;
using JObj = map<string, JVal>;
using JArr = vector<JVal>;

enum JType { J_NULL, J_BOOL, J_NUM, J_STR, J_ARR, J_OBJ };

struct JVal {
    JType type = J_NULL;
    double num = 0;
    bool bval = false;
    string str;
    JArr arr;
    JObj obj;
};

struct JParser {
    const string& s;
    size_t pos = 0;

    void ws() { while (pos < s.size() && isspace((unsigned char)s[pos])) ++pos; }
    char peek() { ws(); return pos < s.size() ? s[pos] : 0; }
    char next() { ws(); return pos < s.size() ? s[pos++] : 0; }
    void expect(char c) {
        if (next() != c) { cerr << "JSON parse error: expected '" << c << "'\n"; exit(1); }
    }

    string parseStr() {
        expect('"');
        string r;
        while (pos < s.size() && s[pos] != '"') {
            if (s[pos] == '\\') {
                ++pos;
                if (pos < s.size()) {
                    char e = s[pos++];
                    switch (e) {
                        case 'n':  r += '\n'; break;
                        case 't':  r += '\t'; break;
                        case '\\': r += '\\'; break;
                        case '"':  r += '"';  break;
                        case '/':  r += '/';  break;
                        default:   r += e;    break;
                    }
                }
            } else {
                r += s[pos++];
            }
        }
        expect('"');
        return r;
    }

    JVal parseVal() {
        JVal v;
        char c = peek();
        if (c == '"')      { v.type = J_STR;  v.str = parseStr(); }
        else if (c == '{') { v.type = J_OBJ;  v.obj = parseObject(); }
        else if (c == '[') { v.type = J_ARR;  v.arr = parseArray(); }
        else if (c == 't') { pos += 4; v.type = J_BOOL; v.bval = true; }
        else if (c == 'f') { pos += 5; v.type = J_BOOL; v.bval = false; }
        else if (c == 'n') { pos += 4; v.type = J_NULL; }
        else {
            v.type = J_NUM;
            size_t start = pos;
            if (s[pos] == '-') ++pos;
            while (pos < s.size() && (isdigit((unsigned char)s[pos]) || s[pos] == '.'
                   || s[pos] == 'e' || s[pos] == 'E' || s[pos] == '+' || s[pos] == '-'))
                ++pos;
            v.num = stod(s.substr(start, pos - start));
        }
        return v;
    }

    JArr parseArray() {
        expect('[');
        JArr a;
        if (peek() != ']') {
            a.push_back(parseVal());
            while (peek() == ',') { next(); a.push_back(parseVal()); }
        }
        expect(']');
        return a;
    }

    JObj parseObject() {
        expect('{');
        JObj o;
        if (peek() != '}') {
            string k = parseStr(); expect(':'); o[k] = parseVal();
            while (peek() == ',') { next(); k = parseStr(); expect(':'); o[k] = parseVal(); }
        }
        expect('}');
        return o;
    }

    JVal parse() { return parseVal(); }
};

JVal jsonParse(const string& s) { JParser p{s}; return p.parse(); }

// ---- JVal -> C++ type converters -----------------------------------------
int         jToInt(const JVal& v)    { return (int)v.num; }
long long   jToLong(const JVal& v)   { return (long long)v.num; }
double      jToDouble(const JVal& v) { return v.num; }
bool        jToBool(const JVal& v)   { return v.bval; }
string      jToString(const JVal& v) { return v.str; }
char        jToChar(const JVal& v)   { return v.str.empty() ? '\0' : v.str[0]; }

vector<int>    jToVecInt(const JVal& v) {
    vector<int> r; for (auto& e : v.arr) r.push_back(jToInt(e)); return r;
}
vector<long long> jToVecLong(const JVal& v) {
    vector<long long> r; for (auto& e : v.arr) r.push_back(jToLong(e)); return r;
}
vector<double> jToVecDouble(const JVal& v) {
    vector<double> r; for (auto& e : v.arr) r.push_back(jToDouble(e)); return r;
}
vector<string> jToVecString(const JVal& v) {
    vector<string> r; for (auto& e : v.arr) r.push_back(jToString(e)); return r;
}
vector<char>   jToVecChar(const JVal& v) {
    vector<char> r; for (auto& e : v.arr) r.push_back(jToChar(e)); return r;
}
vector<bool>   jToVecBool(const JVal& v) {
    vector<bool> r; for (auto& e : v.arr) r.push_back(jToBool(e)); return r;
}
vector<vector<int>> jToVecVecInt(const JVal& v) {
    vector<vector<int>> r; for (auto& e : v.arr) r.push_back(jToVecInt(e)); return r;
}
vector<vector<string>> jToVecVecString(const JVal& v) {
    vector<vector<string>> r; for (auto& e : v.arr) r.push_back(jToVecString(e)); return r;
}
vector<vector<char>> jToVecVecChar(const JVal& v) {
    vector<vector<char>> r; for (auto& e : v.arr) r.push_back(jToVecChar(e)); return r;
}

// ---- C++ value -> JSON string serialization ------------------------------
string toJson(int v)       { return to_string(v); }
string toJson(long long v) { return to_string(v); }
string toJson(double v)    { ostringstream o; o << v; return o.str(); }
string toJson(bool v)      { return v ? "true" : "false"; }
string toJson(const string& v) {
    string r = "\"";
    for (char c : v) {
        if (c == '"') r += "\\\"";
        else if (c == '\\') r += "\\\\";
        else if (c == '\n') r += "\\n";
        else r += c;
    }
    return r + "\"";
}
string toJson(char v) { string s(1, v); return toJson(s); }

template<typename T>
string toJson(const vector<T>& v) {
    string r = "[";
    for (size_t i = 0; i < v.size(); ++i) { if (i) r += ","; r += toJson(v[i]); }
    return r + "]";
}
// ---- end helpers ---------------------------------------------------------
"""

# C++ type -> converter function name
_CPP_TYPE_CONVERTER = {
    "int":                      "jToInt",
    "long long":                "jToLong",
    "double":                   "jToDouble",
    "float":                    "jToDouble",
    "bool":                     "jToBool",
    "string":                   "jToString",
    "char":                     "jToChar",
    "vector<int>":              "jToVecInt",
    "vector<long long>":        "jToVecLong",
    "vector<double>":           "jToVecDouble",
    "vector<string>":           "jToVecString",
    "vector<char>":             "jToVecChar",
    "vector<bool>":             "jToVecBool",
    "vector<vector<int>>":      "jToVecVecInt",
    "vector<vector<string>>":   "jToVecVecString",
    "vector<vector<char>>":     "jToVecVecChar",
}


def _normalize_cpp_type(raw: str) -> str:
    """Strip const, &, leading/trailing whitespace and collapse spaces."""
    t = raw.strip()
    t = re.sub(r'\bconst\b', '', t)
    t = t.replace('&', '')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _split_cpp_param(param_str: str) -> tuple[str, str]:
    """Split e.g. ``vector<int>& nums`` -> ``('vector<int>', 'nums')``."""
    param_str = param_str.strip()
    # Last whitespace-delimited token is the name; everything before is the type.
    parts = param_str.rsplit(None, 1)
    if len(parts) == 2:
        return _normalize_cpp_type(parts[0]), parts[1]
    return _normalize_cpp_type(parts[0]), "arg"


def _parse_cpp_signature(student_code: str) -> tuple[str, str, list[tuple[str, str]]]:
    """Extract ``(return_type, method_name, [(type, name), ...])`` from a Solution class.

    Handles nested template types like ``vector<vector<int>>``.
    Skips constructors named ``Solution``.
    """
    sig_re = re.compile(
        r'(?:public\s*:\s*\n?)?'       # optional "public:"
        r'\s+([\w<>, ]+?)\s+'           # return type  (group 1)
        r'(\w+)\s*'                     # method name  (group 2)
        r'\(\s*(.*?)\s*\)',             # params       (group 3)
        re.DOTALL,
    )
    m = sig_re.search(student_code)
    if not m:
        raise ValueError("Cannot extract C++ method signature from student code")

    ret_type = _normalize_cpp_type(m.group(1))
    method_name = m.group(2)
    raw_params = m.group(3).strip()

    # Skip constructor
    if method_name == "Solution":
        remaining = student_code[m.end():]
        m2 = sig_re.search(remaining)
        if not m2:
            raise ValueError("Cannot extract C++ method signature (found constructor only)")
        ret_type = _normalize_cpp_type(m2.group(1))
        method_name = m2.group(2)
        raw_params = m2.group(3).strip()

    # Parse param list — split on commas NOT inside angle brackets.
    params: list[tuple[str, str]] = []
    if raw_params:
        depth = 0
        current = ""
        for ch in raw_params:
            if ch == '<':
                depth += 1
            elif ch == '>':
                depth -= 1
            if ch == ',' and depth == 0:
                params.append(_split_cpp_param(current.strip()))
                current = ""
            else:
                current += ch
        if current.strip():
            params.append(_split_cpp_param(current.strip()))

    return ret_type, method_name, params


def _cpp_converter_expr(cpp_type: str, json_accessor: str) -> str:
    """Return a C++ expression that converts a JVal to *cpp_type*."""
    conv = _CPP_TYPE_CONVERTER.get(cpp_type)
    if conv:
        return f"{conv}({json_accessor})"
    # Fallback to int
    return f"jToInt({json_accessor})"


def _build_cpp_wrapper(student_code: str, tc_input: dict | str, tc_expected) -> tuple[str, str, str]:
    """Build a self-contained C++ program that runs the student's Solution against one test case.

    Returns ``(full_cpp_code, stdin_str, expected_str)``.
    """
    ret_type, method_name, params = _parse_cpp_signature(student_code)

    # ── stdin / expected ────────────────────────────────────────────────
    if isinstance(tc_input, dict):
        stdin_str = json.dumps(tc_input)
    else:
        stdin_str = str(tc_input)

    expected_str = _normalize_expected(tc_expected)

    # ── headers ─────────────────────────────────────────────────────────
    headers = """\
#include <iostream>
#include <vector>
#include <string>
#include <map>
#include <unordered_map>
#include <unordered_set>
#include <set>
#include <algorithm>
#include <queue>
#include <stack>
#include <sstream>
#include <climits>
#include <cmath>
#include <cctype>
#include <numeric>
using namespace std;
"""

    # ── optional struct stubs ───────────────────────────────────────────
    structs = ""
    if "TreeNode" in student_code:
        structs += """\
struct TreeNode {
    int val;
    TreeNode *left;
    TreeNode *right;
    TreeNode() : val(0), left(nullptr), right(nullptr) {}
    TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}
    TreeNode(int x, TreeNode *l, TreeNode *r) : val(x), left(l), right(r) {}
};
"""
    if "ListNode" in student_code:
        structs += """\
struct ListNode {
    int val;
    ListNode *next;
    ListNode() : val(0), next(nullptr) {}
    ListNode(int x) : val(x), next(nullptr) {}
    ListNode(int x, ListNode *n) : val(x), next(n) {}
};
"""

    # ── main() body ─────────────────────────────────────────────────────
    main_lines: list[str] = []
    main_lines.append('    string _raw((istreambuf_iterator<char>(cin)), istreambuf_iterator<char>());')
    main_lines.append('    JVal _root = jsonParse(_raw);')
    main_lines.append('')

    arg_names: list[str] = []
    for cpp_type, pname in params:
        conv = _cpp_converter_expr(cpp_type, f'_root.obj["{pname}"]')
        main_lines.append(f'    {cpp_type} {pname} = {conv};')
        arg_names.append(pname)

    main_lines.append('')
    main_lines.append('    Solution _sol;')

    call_args = ', '.join(arg_names)
    if ret_type == "void":
        main_lines.append(f'    _sol.{method_name}({call_args});')
        main_lines.append('    cout << "null" << endl;')
    else:
        main_lines.append(f'    auto _result = _sol.{method_name}({call_args});')
        main_lines.append('    cout << toJson(_result) << endl;')

    main_body = '\n'.join(main_lines)

    # ── assemble ────────────────────────────────────────────────────────
    full_code = f"""{headers}
{structs}
{_CPP_JSON_PARSER}

// ---- student code ----
{student_code}
// ---- end student code ----

int main() {{
{main_body}
    return 0;
}}
"""
    return full_code.strip(), stdin_str, expected_str


def _build_wrapper(code: str, language: str, tc_input, tc_expected) -> tuple[str, str, str]:
    """Route to the correct language wrapper."""
    if language in ("python", "python3"):
        return _build_python_wrapper(code, tc_input, tc_expected)
    if language in ("javascript", "js"):
        return _build_js_wrapper(code, tc_input, tc_expected)
    if language in ("java",):
        return _build_java_wrapper(code, tc_input, tc_expected)
    if language in ("go", "golang"):
        return _build_go_wrapper(code, tc_input, tc_expected)
    if language in ("cpp", "c++"):
        return _build_cpp_wrapper(code, tc_input, tc_expected)
    if isinstance(tc_input, dict):
        stdin_str = json.dumps(tc_input)
    else:
        stdin_str = str(tc_input)
    return code, stdin_str, _normalize_expected(tc_expected)


async def _run_tests(code: str, language: str, test_cases: list[dict]) -> list[dict]:
    """Run code against test cases via Judge0 with proper wrapping."""
    from app.services.judge0.client import get_judge0_client
    import asyncio

    client = get_judge0_client()

    # Build wrapped submissions for each test case
    submissions = []
    for tc in test_cases:
        tc_input = tc.get("input", tc.get("in", tc.get("stdin", "")))
        tc_expected = tc.get("expected", tc.get("out", tc.get("output", "")))

        wrapped_code, stdin_str, expected_str = _build_wrapper(code, language, tc_input, tc_expected)

        submissions.append({
            "code": wrapped_code,
            "stdin": stdin_str,
            "expected": expected_str,
            "tc_input": tc_input,
            "tc_expected": tc_expected,
        })

    # Submit all to Judge0 in parallel
    tokens = await asyncio.gather(*[
        client.submit(
            code=sub["code"],
            language=language,
            stdin=sub["stdin"],
            expected_output=sub["expected"],
        )
        for sub in submissions
    ])

    # Poll results
    await asyncio.sleep(0.5)
    raw_results = await asyncio.gather(*[
        client.poll(token) for token in tokens
    ], return_exceptions=True)

    # Format results
    results = []
    for i, (sub, raw) in enumerate(zip(submissions, raw_results)):
        if isinstance(raw, Exception):
            results.append({
                "index": i,
                "input": str(sub["tc_input"]),
                "expected": str(sub["tc_expected"]),
                "actual": "",
                "passed": False,
                "error": str(raw),
                "time_ms": 0,
                "memory_kb": 0,
            })
            continue

        status_id = raw.get("status", {}).get("id", 0)
        stdout = (raw.get("stdout") or "").strip()
        stderr = (raw.get("stderr") or "").strip()

        # Try to parse and compare as JSON for structured outputs
        passed = status_id == 3  # Judge0 "Accepted"
        if not passed and stdout:
            try:
                actual_parsed = json.loads(stdout)
                expected_parsed = sub["tc_expected"]
                if isinstance(expected_parsed, str):
                    try:
                        expected_parsed = json.loads(expected_parsed)
                    except (json.JSONDecodeError, TypeError):
                        pass
                passed = actual_parsed == expected_parsed
            except (json.JSONDecodeError, TypeError):
                pass

        # Format input for display
        input_display = sub["tc_input"]
        if isinstance(input_display, dict):
            input_display = ", ".join(f"{k}={json.dumps(v)}" for k, v in input_display.items())
        else:
            input_display = str(input_display)

        expected_display = sub["tc_expected"]
        if isinstance(expected_display, (list, dict)):
            expected_display = json.dumps(expected_display)

        results.append({
            "index": i,
            "input": str(input_display)[:200],
            "expected": str(expected_display),
            "actual": stdout[:500],
            "passed": passed,
            "status": raw.get("status", {}).get("description", "Unknown"),
            "error": stderr or raw.get("compile_output", ""),
            "time_ms": round(float(raw.get("time", 0) or 0) * 1000),
            "memory_kb": raw.get("memory", 0) or 0,
        })

    return results


@router.post("/run")
async def run_code(request: Request):
    """Run code against first 3 test cases via Judge0."""
    user = await get_optional_user(request)
    body = await request.json()

    code = body.get("code", "")
    language = body.get("language", "python")
    test_cases = body.get("test_cases", [])[:3]

    if not code.strip():
        return {"error": "No code provided", "results": []}
    if not test_cases:
        return {"error": "No test cases", "results": []}

    try:
        results = await _run_tests(code, language, test_cases)
        passed = sum(1 for r in results if r.get("passed"))
        total = len(results)
        log.info("[Judge] run user=%s lang=%s passed=%d/%d",
                 user.get("email", "?")[:20], language, passed, total)
        return {"results": results, "passed": passed, "total": total, "all_passed": passed == total}
    except Exception as e:
        log.warning("[Judge] run failed: %s", e)
        return {"error": str(e), "results": []}


@router.post("/submit")
async def submit_code(request: Request):
    """Submit code against ALL test cases via Judge0."""
    user = await get_optional_user(request)
    body = await request.json()

    code = body.get("code", "")
    language = body.get("language", "python")
    test_cases = body.get("test_cases", [])

    if not code.strip():
        return {"error": "No code provided", "results": []}
    if not test_cases:
        return {"error": "No test cases", "results": []}

    try:
        results = await _run_tests(code, language, test_cases)
        passed = sum(1 for r in results if r.get("passed"))
        total = len(results)
        log.info("[Judge] submit user=%s lang=%s passed=%d/%d",
                 user.get("email", "?")[:20], language, passed, total)
        return {"results": results, "passed": passed, "total": total, "all_passed": passed == total}
    except Exception as e:
        log.warning("[Judge] submit failed: %s", e)
        return {"error": str(e), "results": []}
