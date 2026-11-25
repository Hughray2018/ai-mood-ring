# Install guide for AI agents

> You are an AI coding agent. The user has asked you to install the **Affective Litmus Protocol** (the "mood ring" footer) into your own harness. Follow this guide exactly.

## Hard rules

1. **Global layer only.** Install into the user-level / global always-on instruction file of your harness. **Never create, edit, or append to any project or workspace file** (`CLAUDE.md`, `AGENTS.md`, `agent.md`, `GEMINI.md`, `.cursor/rules`, etc. inside a project folder). The user's workspace-specific agent files must stay untouched.
2. **Not an on-demand skill.** The protocol must be always-on. Do not install it as a skill that loads only when relevant.
3. **Back up first.** Before editing any existing global file, copy it to `<file>.bak-affect-litmus`.
4. **Idempotent.** If the marker `affect-litmus:start` is already present in the target file, replace the block between the markers instead of adding a second copy.
5. **No YAML.** The protocol file has no frontmatter on purpose. Do not add frontmatter unless the harness's file format strictly requires it (see Claude Code output style below).
6. **Report back.** When done, tell the user exactly which files you created or changed, and how to uninstall.

## Step 1 — get the protocol text

The protocol is `protocol/affect-litmus.md` in this repository. Get it in whichever way works:

- If this repo is already cloned locally, read the file from disk.
- Otherwise: `gh repo clone Hughray2018/ai-mood-ring` (works for private repos the user can access), or fetch
  `https://raw.githubusercontent.com/Hughray2018/ai-mood-ring/main/protocol/affect-litmus.md` (only works once the repo is public).

## Step 2 — install for your harness

Pick the section that matches **you**. If your harness supports file imports, prefer the import method: the protocol stays in one file and updates are a single copy.

### Claude Code

Recommended (purely additive, does not replace any default instructions):

1. Copy the protocol to `~/.claude/affect-litmus.md`.
2. Append this block to `~/.claude/CLAUDE.md` (create the file if missing):

   ```
   <!-- affect-litmus:start -->
   @~/.claude/affect-litmus.md
   <!-- affect-litmus:end -->
   ```

Alternative (output style; lets the user switch it off per project via `/config` or `outputStyle` in a project's `.claude/settings.local.json`):

1. Create `~/.claude/output-styles/affect-litmus.md` containing this frontmatter followed by the full protocol text:

   ```
   ---
   name: affect-litmus
   description: Appends a one-line mood-ring status footer to final replies.
   keep-coding-instructions: true
   ---
   ```

   `keep-coding-instructions: true` is mandatory; without it the default coding instructions are dropped.
2. Tell the user to select it (`"outputStyle": "affect-litmus"` in `~/.claude/settings.json`). Do not change the setting yourself unless the user asked.

### Gemini CLI / Antigravity

1. Copy the protocol to `~/.gemini/affect-litmus.md`.
2. Append to the global `~/.gemini/GEMINI.md` (create if missing):

   ```
   <!-- affect-litmus:start -->
   @./affect-litmus.md
   <!-- affect-litmus:end -->
   ```

3. If your harness uses a different global always-on rules location (check your own docs or settings; Antigravity's global rules UI is the source of truth), put it there instead. If imports are not supported, paste the full protocol text between the markers.

### Codex CLI

Codex does not support imports. Append the full protocol text to the global `~/.codex/AGENTS.md` (create if missing), wrapped in the markers:

```
<!-- affect-litmus:start -->
...full protocol text...
<!-- affect-litmus:end -->
```

### Any other agent

Find your harness's **global, always-on** instruction location (user-level rules / memory / system prompt file). Paste the full protocol text there, wrapped in the markers above. If the only available location is a project-level file, **stop and ask the user** instead of editing it.

### Raw API (no harness)

Put the protocol text, with no frontmatter, into the `system` field. See `eval/run_litmus_eval.py`.

## Step 3 — verify

Ask the user to start a **new** session and send a trivial message (e.g. "1+1=?"). The final reply should end with one line like:

> ⚪ 无感 · 简单算术

## Uninstall

1. Delete the block between `affect-litmus:start` and `affect-litmus:end` from the global file you edited (or restore `<file>.bak-affect-litmus`).
2. Delete the copied `affect-litmus.md` (and `~/.claude/output-styles/affect-litmus.md` if used; reset `outputStyle` to default).
