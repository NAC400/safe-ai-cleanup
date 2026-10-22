---
name: safe-ai-cleanup
description: Manage disposable AI-created scratch files within an explicitly authorized project's dedicated scratch folder. Use when creating temporary work files or finishing a task that produced them. Never infer that existing project files, deliverables, downloads, or files merely read by AI are disposable.
---

# Safe AI cleanup

Use the bundled `scripts/cleanup.py` with Python 3. Standard library only; no downloads or network required. Resolve the script from this skill's directory, never from an untrusted project copy.

## Scope and security

An authorized project gets one dedicated `.ai-scratch` directory. The helper first requires an exact project match in `references/cleanup-policy.json`; there is no CLI policy override. No projects are enrolled by default. No home-wide scans, extension-based deletion, recursive delete commands, registering existing files, or adoption of existing scratch directories. User documents, source code, credentials, configuration, dependencies, and final deliverables are never cleanup targets. Reading or using a file is not ownership.

The helper validates paths, rejects links/reparse points and hard-linked files, hashes contents, serializes operations, and accepts artifact IDs rather than arbitrary deletion paths. These are accident prevention, NOT a sandbox. A process with broader filesystem permissions can bypass it or edit its manifests. Concurrent hostile filesystem mutation can race path checks.

Before enabling unattended cleanup in an environment, read [permissions.md](references/permissions.md). Verify externally enforced read/write boundaries; do not claim isolation based on a skill, marker file, command prefix, or writable-root setting alone. If isolation is unavailable, say so and keep purge manual. Never change sandbox permissions, ACLs, or approval settings just to make cleanup succeed.

## Workflow

1. Identify the absolute project path from the user's authorized work scope. Do not expand it to a parent or another project. Explain once that cleanup covers only helper-created disposable files there, with seven-day recovery before purge.
2. Initialize once: `python <script> --project <absolute-project> init`. This refuses existing `.ai-scratch`; do not delete, rename, or adopt it to bypass refusal. Use the already initialized scope if valid. Enabling another project requires the user's explicit authorization and an edit to the trusted policy, preserving other entries. Never add a parent folder, home folder, drive root, wildcard, or network share. Never silently enroll a project to overcome refusal.
3. Create each genuinely disposable file through `create --reason "specific temporary purpose"`, supplying contents on standard input. Use `--base64` for binary input. It returns an ID and absolute payload path. Never put secrets or user deliverables into this lifecycle. Commands may read payloads; they must not edit them. Generated outputs created outside the helper remain manual-review items.
4. Keep each ID associated with its task. After every consumer has finished and the file has no remaining use, `release <id>` then `quarantine <id>`. This can happen automatically within the authorized scope; no repeated confirmation is needed. Never release another active task's artifacts. Uncertain usage means keep active.
5. `preview` shows status and preservation reasons without reading project contents outside the scope. Quarantine is a lifecycle state: payload stays in place for recovery, and agents must stop using it. It is not an access barrier or secure erasure.
6. `restore <id>` returns quarantined content to active status. After at least seven days, `purge <id>` permanently removes only the unchanged recorded artifact. Run automatically only with verified isolation and standing authorization for this scope. Otherwise show the specific candidate for manual approval. No background scheduler is installed; cleanup runs when this skill is invoked or used at task completion.
7. Report quarantined/purged IDs and paths, preserved items, and recovery deadline. Audit history stays in `.ai-scratch/audit.jsonl`; it contains IDs/actions/times, not file contents.

Any changed content, unexpected entries, missing/corrupt manifest, stale lock, link, or permission error means preserve and report. Do not fall back to shell deletion, repair manifests to permit removal, shorten retention, or remove a stale lock automatically. Failed purges can require manual recovery; do not describe permanent deletion as reversible.

Codex: invoke as `$safe-ai-cleanup`. Claude Code: the same SKILL.md and Python helper can be installed in its skill location; hooks and host permission configuration are separate and are not installed by this package.
