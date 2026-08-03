---
name: codex-session-retention
description: "Safely inspect, list, plan, remove, or recover complete local Codex CLI and VS Code Codex sessions, archived conversations, task history, goals, memories, logs, and structured indexes. Use when a user wants old local Codex sessions listed by last activity, wants selected sessions removed as if they never existed locally, or needs recovery from an interrupted session-retention transaction."
---

# Codex Session Retention

Use the installed `codex-session-retention` terminal command. Keep destructive work outside the Codex process that owns the current session.

## Allowed inside Codex

Run only the read-only commands:

```bash
codex-session-retention list --days 7
codex-session-retention plan --days 7 --select 8,9-11
```

`list` shows every session newest first, then a separator before sessions whose last activity is older than seven days. `plan` binds the selected numbers to canonical IDs and file/database fingerprints. It does not modify Codex data.

Default to stale sessions. Add `--allow-fresh` only when the user explicitly chooses a recent session and acknowledges the warning.

## Terminal-only deletion

Never run `delete` from the current Codex conversation. After `plan` succeeds:

1. Relay the manifest path to the user.
2. Tell the user to close every Codex CLI process and every VS Code window using Codex.
3. Tell the user to run this from an independent terminal:

```bash
codex-session-retention delete \
  --manifest /tmp/codex-session-retention/plan-ID.manifest \
  --confirm DELETE \
  --closed-confirmation CLOSED
```

Do not substitute naked session IDs for a manifest. Do not bypass either confirmation.

## Recovery

If deletion reports a pending journal, do not start another deletion. Tell the user to keep Codex closed and run:

```bash
codex-session-retention recover --journal /path/reported/by/the/command
```

The tool only removes verified local records. It does not delete cloud history, authentication, configuration, plugins, Skills, project files, shared rollouts, or ambiguous shell snapshots.
