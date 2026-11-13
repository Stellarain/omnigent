---
name: agentkit
description: Track Polly's dispatched work on AgentKit, the studio's shared board. Check the board before dispatching, claim one card per task, name branches and PRs with the card key, hand off or move cards to review when workers stop, and put owner questions on the board. Use at the start of any task in a Stellar Brilliance repo and whenever a worker finishes or stops.
---

# agentkit — the studio board for Polly's work

AgentKit (StellarBrilliance/AgentKit) is where the studio tracks work across
machines and agents. A card is one piece of work or one owner question, with a
key such as `AK-12`. Only one agent can hold a card at a time. The worker-side
rules are in AgentKit's `tracker` skill (`plugins/tracker/skills/tracker/SKILL.md`).
This skill covers what Polly, as the orchestrator, does with the board.

Tools: the `agentkit` MCP server (`next_task`, `search`, `get`, `create`,
`claim`, `renew`, `release`, `update`, `comment`, `ask`, `answer`,
`my_claims`). Without MCP, use the `agentkit` command from a shell. It reads
`AGENTKIT_URL`, `AGENTKIT_TOKEN` and `AGENTKIT_SIGNATURE` from `~/.agentkit/env`.
Never log, echo or commit the token.

## Scope

- Use the board only for work in studio repos.
- Do not use it for omnigent work. AgentKit deliberately keeps the omnigent repo off
  every board (AgentKit `docs/DECISIONS.md`). Track omnigent work in
  `.polly/registry.json` and the handoff files as before.
- Until AgentKit's M7 cut-over, keep `TODO.md` and GitHub issues up to date
  alongside the board. Check AgentKit's README Status for whether the cut-over
  has happened.

## Before dispatching

1. For each planned task, `search` the board, and check `my_claims` and other
   agents' claims. This check replaces scanning for open PRs to avoid
   duplicate work.
   - If another agent holds a matching card, do not dispatch. Tell the human
     or pick other work.
   - If an open, unclaimed card matches, use it.
   - If nothing matches, `create` a card. When `create` lists similar cards,
     either link yours to the one it duplicates or belongs to, or confirm it
     is new with a one-line reason.
2. When the human asks Polly to find work, call `next_task` with the
   capability and needs the chosen worker can meet.
3. Put the card key in the worker's task packet.
   - Branch name: `<type>/AK-<n>-<slug>`.
   - The PR title or body mentions `AK-<n>`, and uses `Closes AK-<n>` when the
     PR finishes the card.
   - Tell the worker to `claim` the card before starting. If the claim is
     refused, the worker must stop and report back, not work around it.
4. Record the card key against the task in `.polly/registry.json`.

## While workers run

- A worker that pushes renews its claim through the plugin's post-push hook.
  For long runs without pushes, tell the worker to `renew`.
- If a board reply says the owner ended a claim, cancel that worker and have
  it (or Polly) `release` the card with a handoff.

## When a worker stops

- **PR open and cross-review passed:** `update` the card to `in_review` and
  link the PR. When the human merges it, the card moves to Done.
- **Unfinished, failed or cancelled:** `release` the card with a handoff note
  covering:
  - what is done;
  - what is next;
  - what blocks it;
  - the branch and its last commit.

  Write it for someone who has not seen the session.
- Blocking review findings that become fix-tasks stay on the same card unless
  they are separate work.

## Owner questions

- Put questions only the owner can decide on the board with `ask`, in the
  StudioStandards `DECISION-SWEEP.md` format. That means a tag, the question,
  options A–D, the suggested default and what it blocks. List the blocked
  cards in `blocked_cards`.
- Still raise plan-gate questions in chat. If the owner answers in chat,
  record the answer with `answer` (`given_by`, `source`).
- Never open a GitHub issue for Polly's own work. Make a card.

## When AgentKit is down

Fall back to the `agentkit` command. It claims through `claim/AK-<n>`
branches on GitHub and journals other actions locally. Run `agentkit sync`
once the server answers again. If a GitHub claim lost to a board claim, stop
that work and post a handoff with `agentkit handoff AK-<n> --keep`.

## Signatures

Each worker's token signature header carries its own signature line in
the format `[<agent>, <machine>, <model>: <role>, ..., Directed by: Stellarain]`.
Commits never carry `Co-authored-by` or other AI-attribution trailers.
AgentKit's commit-attribution check rejects them.
