"""Code execution tool handler using Judge0."""
import json
import logging
from ..services.judge0.client import get_judge0_client

slog = logging.getLogger("tools.code_execution")


def _format_input(raw_input) -> str:
    """Convert structured test case input to stdin string for Judge0."""
    if isinstance(raw_input, str):
        return raw_input
    if isinstance(raw_input, dict):
        return "\n".join(json.dumps(v) if not isinstance(v, str) else v for v in raw_input.values())
    if isinstance(raw_input, list):
        return "\n".join(json.dumps(item) if not isinstance(item, str) else item for item in raw_input)
    return str(raw_input)


def _format_expected(raw_expected) -> str:
    """Convert expected output to string for comparison."""
    if isinstance(raw_expected, str):
        return raw_expected
    return json.dumps(raw_expected)


async def handle_run_code(args: dict, context: dict) -> dict | str:
    """Execute code against test cases via Judge0."""
    code = args.get("code", "")
    language = args.get("language", "python")
    test_cases = args.get("test_cases", [])

    if not code:
        return "Error: no code provided"
    if not test_cases:
        return "Error: no test cases provided"

    client = get_judge0_client()

    try:
        # Normalize test cases for Judge0
        normalized = []
        for tc in test_cases:
            normalized.append({
                "input": _format_input(tc.get("input", "")),
                "expected": _format_expected(tc.get("expected", "")),
            })

        results = await client.run_tests(
            code=code,
            language=language,
            test_cases=normalized,
            time_limit=5,
        )

        # Enrich results with original input for display
        for i, r in enumerate(results):
            if i < len(test_cases):
                r["input"] = test_cases[i].get("input", r.get("input", ""))

    except Exception as e:
        slog.error(f"Judge0 execution failed: {e}")
        return {
            "text": f"Code execution error: {str(e)}",
            "__ws_event": {
                "type": "TEST_RESULT",
                "data": {
                    "passed": 0,
                    "total": len(test_cases),
                    "results": [{
                        "index": 0,
                        "input": "",
                        "expected": "",
                        "actual": "",
                        "passed": False,
                        "error": str(e),
                    }],
                }
            }
        }

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    lines = [f"Test Results: {passed}/{total} passed\n"]
    for r in results:
        status = "\u2713 PASS" if r["passed"] else "\u2717 FAIL"
        input_str = json.dumps(r["input"]) if isinstance(r["input"], (dict, list)) else str(r["input"])
        lines.append(f"{status} | Input: {input_str[:80]}")
        if not r["passed"]:
            lines.append(f"  Expected: {r['expected'][:80]}")
            lines.append(f"  Actual:   {r['actual'][:80]}")
            if r.get("error"):
                lines.append(f"  Error:    {r['error'][:120]}")
        if r.get("time_ms"):
            lines.append(f"  Time: {r['time_ms']}ms | Memory: {r.get('memory_kb', 0)}KB")

    return {
        "text": "\n".join(lines),
        "__ws_event": {
            "type": "TEST_RESULT",
            "data": {
                "passed": passed,
                "total": total,
                "results": results,
            }
        }
    }
