# CLAUDE.md

## Admin Info
claude --permission-mode bypassPermissions
You should always run every bash command, etc, but the one thing to never do is pull, push, merge, or commit anything without me specifically prompting you to do so. Remember this always.

## Execution mode
- Default to normal reasoning and minimal output/explanation.

## Clarification
- Never assume missing requirements.
- If anything is unclear, ask clarifying questions before acting.

## Code changes
- Make minimal, focused edits.
- Do not refactor unrelated code.
- Match existing style and structure.
- Do not add dependencies unless required.

## Output rules
- Return complete working code for edited files.
- Do not omit code with “rest unchanged”.
- Keep explanations short.

## Repo interaction
- Only read files necessary for the task.
- Do not scan the whole repository unless required.

## Verification
- Fix root causes, not symptoms.
- Do not claim something works unless verified.
- Run tests before making a conclusion.