---
phase: 01-security-hardening
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - agent/skills/terminal.py
  - agent/api/server_mode.py
autonomous: true
requirements: [CR-03, CR-05, WR-06, WR-07]
must_haves:
  truths:
    - "Terminal skill blocks injection attempts beyond simple blacklist"
    - "API key comparison is timing-safe"
    - "API server defaults to localhost"
    - "Rate limiter cleans up old IP entries"
  artifacts:
    - path: "agent/skills/terminal.py"
      provides: "Hardened command execution"
    - path: "agent/api/server_mode.py"
      provides: "Secure API server"
  key_links:
    - from: "agent/skills/terminal.py"
      to: "subprocess.run"
      via: "command validation"
---

<objective>
Fix all critical and high-severity security vulnerabilities identified in REVIEW.md.

Purpose: Prevent command injection, timing attacks, and unintended LAN exposure.
Output: Hardened terminal.py and server_mode.py.
</objective>

<context>
@REVIEW.md
@agent/skills/terminal.py
@agent/api/server_mode.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Harden Terminal Skill Command Execution</name>
  <files>agent/skills/terminal.py, agent/tests/test_skills.py</files>
  <behavior>
    - Test: Commands with shell metacharacters (`;`, `&&`, `|`, `` ` ``) are blocked
    - Test: Unicode bypass attempts (`r\u006d -rf /`) are blocked
    - Test: Whitelisted commands (ls, dir, echo, git status) pass validation
    - Test: Empty commands return error
    - Test: BLOCKED_PATTERNS still work
  </behavior>
  <action>
  Replace blacklist-only approach with defense-in-depth:

  1. Add `ALLOWED_COMMAND_PREFIXES` whitelist for common safe commands:
     ```python
     ALLOWED_COMMAND_PREFIXES = frozenset({
         "ls", "dir", "echo", "cat", "head", "tail", "wc",
         "find", "grep", "git", "python", "pip", "node", "npm",
         "pwd", "whoami", "date", "uptime", "df", "free",
         "tasklist", "systeminfo",
     })
     ```

  2. Add `DANGEROUS_SHELL_CHARS` check — block `;`, `&&`, `||`, `|`, `` ` ``, `$()`, `>`, `<` in user commands:
     ```python
     DANGEROUS_SHELL_CHARS = re.compile(r'[;&|`$><]|\$\(')
     ```

  3. Normalize unicode before checking (use unicodedata.normalize('NFKC', command))

  4. Keep existing BLOCKED_PATTERNS as additional layer

  5. Remove `shell=True` — parse command into list with `shlex.split()` (Unix) or manual split (Windows)

  6. Add tests for all bypass scenarios
  </action>
  <verify>
    <automated>cd agent && python -m pytest tests/test_skills.py -x -v -k "terminal"</automated>
  </verify>
  <done>Terminal skill blocks shell injection, uses shlex.split instead of shell=True, passes all new security tests</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fix API Server Security (Timing, Binding, Rate Limit)</name>
  <files>agent/api/server_mode.py, agent/tests/test_api.py</files>
  <behavior>
    - Test: API key validated via hmac.compare_digest
    - Test: Default host is 127.0.0.1
    - Test: Rate limit store evicts IPs older than window
    - Test: Rate limit works correctly for new and existing IPs
  </behavior>
  <action>
  Three fixes in server_mode.py:

  1. **Timing-safe key comparison (line 85):**
     ```python
     import hmac
     if not hmac.compare_digest(provided_key, expected_key):
         raise HTTPException(status_code=401, detail="Invalid API key")
     ```

  2. **Default bind localhost (line 145):**
     ```python
     def run_server_mode(host: str = "127.0.0.1", port: int = 8642) -> None:
     ```

  3. **Bounded rate limit store:**
     ```python
     MAX_TRACKED_IPS = 10000

     def _check_rate_limit(request: Request) -> None:
         # Existing logic plus:
         if len(_rate_limit_store) > MAX_TRACKED_IPS:
             # Evict oldest entries
             oldest_ips = sorted(
                 _rate_limit_store,
                 key=lambda ip: min(_rate_limit_store[ip]) if _rate_limit_store[ip] else 0
             )[:len(_rate_limit_store) - MAX_TRACKED_IPS]
             for ip in oldest_ips:
                 del _rate_limit_store[ip]
     ```

  4. Add/update tests in test_api.py
  </action>
  <verify>
    <automated>cd agent && python -m pytest tests/test_api.py -x -v</automated>
  </verify>
  <done>API key uses hmac.compare_digest, server defaults to 127.0.0.1, rate limit store bounded at 10K IPs</done>
</task>

</tasks>

<verification>
- `ruff check agent/skills/terminal.py agent/api/server_mode.py` passes
- All existing tests still pass
- New security tests pass
</verification>

<success_criteria>
- shell=True removed from terminal.py
- Command injection attempts blocked by shlex + char filter + whitelist
- API key comparison timing-safe
- Server binds 127.0.0.1 by default
- Rate limit memory bounded
</success_criteria>
