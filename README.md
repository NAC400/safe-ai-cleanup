# safe-ai-cleanup

An AI skill for cleaning up its own temporary files without treating your project files as disposable.

- Exact project allowlist; no projects enabled by default.
- Only files created through the helper qualify for cleanup.
- Rejects changed files, hard links, symlinks, and Windows junctions.
- Preview, audit log, quarantine, and restore.
- Permanent deletion only after seven days in quarantine.

This is accident prevention, not an OS sandbox. Unattended deletion requires separately enforced filesystem permissions. See [permissions](references/permissions.md).

## Use

Install this folder as `safe-ai-cleanup` in your agent's skill directory. For Codex, use `~/.agents/skills/safe-ai-cleanup`; for Claude Code, use `~/.claude/skills/safe-ai-cleanup`.

Add an explicitly approved absolute project path to `references/cleanup-policy.json`. Invoke `$safe-ai-cleanup` in Codex or `/safe-ai-cleanup` in Claude Code. Read [SKILL.md](SKILL.md) for the workflow.

Requires Python 3.10+; no third-party packages, downloads, hooks, or background jobs.

## Test

```sh
python -B scripts/test_cleanup.py
```

Tests use disposable fixtures. The Windows junction check runs only on Windows.
