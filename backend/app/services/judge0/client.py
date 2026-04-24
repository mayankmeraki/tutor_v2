import os, base64, asyncio, httpx, logging

slog = logging.getLogger("judge0")

JUDGE0_URL = os.getenv("JUDGE0_URL", "http://localhost:2358")

LANG_IDS = {
    "python": 71,     # Python 3.8.1
    "python3": 71,
    "javascript": 63, # Node.js 12.14.0
    "java": 62,       # Java OpenJDK 13.0.1
    "cpp": 54,        # C++ GCC 9.2.0
    "c": 50,          # C GCC 9.2.0
    "go": 60,         # Go 1.13.5
    "typescript": 74,  # TypeScript 3.7.4
    "rust": 73,       # Rust 1.40.0
}

class Judge0Client:
    def __init__(self, base_url=None):
        self.base_url = (base_url or JUDGE0_URL).rstrip("/")
        self._http = httpx.AsyncClient(timeout=30)

    async def submit(self, code: str, language: str, stdin: str = "",
                     expected_output: str = "", time_limit: float = 5,
                     memory_limit: int = 512000) -> str:
        """Submit code, return submission token."""
        lang_id = LANG_IDS.get(language.lower())
        if not lang_id:
            raise ValueError(f"Unsupported language: {language}")

        payload = {
            "source_code": base64.b64encode(code.encode()).decode(),
            "language_id": lang_id,
            "stdin": base64.b64encode(stdin.encode()).decode() if stdin else "",
            "expected_output": base64.b64encode(expected_output.encode()).decode() if expected_output else "",
            "cpu_time_limit": time_limit,
            "memory_limit": memory_limit,
        }

        resp = await self._http.post(
            f"{self.base_url}/submissions/?base64_encoded=true&wait=false",
            json=payload
        )
        resp.raise_for_status()
        return resp.json()["token"]

    async def poll(self, token: str, max_wait: float = 15, interval: float = 0.5) -> dict:
        """Poll for submission result."""
        elapsed = 0
        while elapsed < max_wait:
            resp = await self._http.get(
                f"{self.base_url}/submissions/{token}?base64_encoded=true&fields=*"
            )
            resp.raise_for_status()
            data = resp.json()
            status_id = data.get("status", {}).get("id", 0)
            # 1=In Queue, 2=Processing
            if status_id > 2:
                # Decode base64 fields
                for field in ("stdout", "stderr", "compile_output", "message"):
                    val = data.get(field)
                    if val:
                        try:
                            data[field] = base64.b64decode(val).decode("utf-8", errors="replace")
                        except Exception:
                            pass
                return data
            await asyncio.sleep(interval)
            elapsed += interval
        raise TimeoutError(f"Judge0 submission {token} timed out after {max_wait}s")

    async def run_tests(self, code: str, language: str, test_cases: list[dict],
                        time_limit: float = 5) -> list[dict]:
        """Run code against multiple test cases. Returns list of results."""
        # Submit all test cases in parallel
        tokens = await asyncio.gather(*[
            self.submit(
                code=code,
                language=language,
                stdin=tc.get("input", ""),
                expected_output=str(tc.get("expected", "")),
                time_limit=time_limit,
            )
            for tc in test_cases
        ])

        # Brief pause then poll all
        await asyncio.sleep(0.5)
        raw_results = await asyncio.gather(*[
            self.poll(token) for token in tokens
        ], return_exceptions=True)

        results = []
        for i, (tc, raw) in enumerate(zip(test_cases, raw_results)):
            if isinstance(raw, Exception):
                results.append({
                    "index": i,
                    "input": tc.get("input", ""),
                    "expected": str(tc.get("expected", "")),
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
            expected = str(tc.get("expected", "")).strip()

            # Status 3 = Accepted, 4 = Wrong Answer, 5 = TLE, 6 = Compilation Error, etc.
            passed = status_id == 3

            results.append({
                "index": i,
                "input": tc.get("input", ""),
                "expected": expected,
                "actual": stdout,
                "passed": passed,
                "status": raw.get("status", {}).get("description", "Unknown"),
                "error": stderr or raw.get("compile_output", ""),
                "time_ms": round(float(raw.get("time", 0) or 0) * 1000),
                "memory_kb": raw.get("memory", 0) or 0,
            })

        return results

    async def close(self):
        await self._http.aclose()


# Singleton
_client = None

def get_judge0_client() -> Judge0Client:
    global _client
    if _client is None:
        _client = Judge0Client()
    return _client
