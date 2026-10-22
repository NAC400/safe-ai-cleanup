# Enforcing folder boundaries

The skill and helper cannot restrict the agent's other tools or the Python process's OS identity. The bundled cleanup-policy.json enforces an exact project allowlist inside this helper, but is not OS access control. Keep the installed script and policy outside agent-writable roots; changes require the user's permission. A copied/modified helper can bypass this check if the host permits executing it. The helper intentionally does not accept a user-supplied source file to read: creation consumes standard input.

For a strong cleanup boundary, execute cleanup in a separate OS-enforced environment with only the designated `.ai-scratch` folder mounted writable. Expose the trusted script/runtime read-only; do not expose the rest of the project, home directory, credentials, or network. The cleanup identity must not be able to modify its permission policy or elevate itself. Runtime/system files needed to execute Python remain accessible; promise isolation of user data, not literally zero other file reads.

For multiple projects, use separately configured cleanup scopes. A coding agent may need broader project access; that is a separate permission profile from its restricted cleanup process. If the agent can launch an unrestricted process or access an unrestricted connector, restricting this helper does not restrict that route.

Before unattended purge, verify permitted create/read/delete within a test scratch mount and denied read/write/delete against sentinel files outside it. Also test symlinks/junctions, hard links, alternate path spellings, subprocesses, and attempts to change policy. Test in a disposable environment, never against valuable files. Configure enforcement outside the agent-writable project; a writable manifest cannot grant permissions.

On Windows, confirm that the selected sandbox supports denied read paths; workspace-write alone is not proof of read isolation. Configure and test the actual host separately. This package does not install an OS sandbox or assert that current permissions satisfy these requirements.

References checked 22 October 2026:
- [OpenAI Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox)
- [Agent approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing)
