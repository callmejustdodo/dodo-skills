---
name: product-planning
description: "Interview the user and review one document at a time to turn a product idea into seven ordered planning documents, an approved HTML mockup, and an AI implementation plan under documentations/. Use when the user wants guided product planning (one-pager, PRD, user stories, screens and flows, tech spec, architecture, implementation plan) or wants to resume an existing planning workflow. Triggers: 제품 기획, 기획해줘, 기획서 써줘, PRD 써줘, MVP 기획, 원페이저, 유저 스토리, 화면 설계, 'help me plan my product', 'write a PRD'."
metadata:
  version: 1.0.0
  openclaw:
    category: "productivity"
---

# Product Planning Interview

Understand the user's intent through a substantive interview, then express it in documents. The user makes product decisions; you choose the questions, write the artifacts, and keep them consistent. Own the workflow so the user does not have to request each document. Finish with an executable implementation plan; implement the product only when asked.

## Terms

- **The user:** the person you are interviewing, the product owner who makes the decisions.
- **End users:** the people who will use the product.
- **Confirmation** is the user's acceptance of a presented document; **approval** is the user's acceptance of a presented mockup revision. Both follow the [review gates](#review-gates). Neither is evidence of market or product validation.

## Language

Ask questions and reply in the user's language unless they request another. Write every Markdown file under `documentations/` in English, whatever language the conversation uses, including the progress record and review notes. When recording the user's own words as evidence, quote them as written and add an English gloss. In mockups, write annotations, preview controls, and sample-data labels in English, and write product UI copy in the end users' language; ask if that is still open.

## Deliverables

Write these files under the target project's root, in this order. Keep the directory name `documentations` and all filenames unchanged.

```text
documentations/
├── 0_one_pager.md
├── 1_product_requirements_documentation.md
├── 2_user_stories.md
├── 3_screen_list_and_user_flows.md
├── mockups/
│   └── index.html
├── 4_techspec.md
├── 5_frontend_architecture.md
├── 6_backend_architecture.md
└── implementation_plan.md
```

Read the matching stage in [references/document-guide.md](references/document-guide.md) when writing each document, and [references/mockup-review.md](references/mockup-review.md) before creating or revising mockups. Link to upstream information instead of duplicating it. Consult [references/skill-options.md](references/skill-options.md) only when a stage would benefit from a supplementary skill; the workflow works without them.

## Review gates

These rules govern every stage. Other sections and references point here instead of restating them.

1. **One document at a time.** Draft only the current document. Reading downstream material for consistency is fine; drafting it early is not.
2. **Present and stop.** Save the draft, link it, summarize its key decisions in a few lines, and ask the user to confirm it or name changes. Stop even when nothing is missing, including when the user supplied every answer up front. For example, in the user's language:
   > `2_user_stories.md` is ready: [link]. Key decisions: … Still open: … Does this match what you want, or what should change?
3. **Count only explicit acceptance.** An unambiguous acceptance of the presented content counts; no special phrase is needed. These do not count: silence, an answer to a discovery question, delegated routine choices, a request to produce all deliverables, your own review, or an automated check. When feedback is ambiguous, name the unresolved point and ask.
4. **Changed content returns to review.** Feedback goes back into the same document; present the changed content again. After confirmation, record the evidence in the [progress record](#progress-record) and start the next stage without waiting for a separate command.
5. **The mockup has its own gate.** After document 3 is confirmed, build the mockup and obtain approval of a named revision before drafting document 4. Confirming a document never approves an unseen mockup. If building or revising the mockup changes document 3's content above its review record, present those changes with the mockup revision and ask one question covering both. This is part of the mockup gate, not a batch. Record the confirmation and the approval separately; if the user accepts only one, the other stays awaiting review, and document 4 waits until both are accepted.
6. **Bookkeeping does not reopen review.** The `## Planning progress` section of `0_one_pager.md` and the `## Mockup review record` section of `3_screen_list_and_user_flows.md` change as the workflow runs. Keep each as the last section of its file. Edits limited to these sections, or to TASK `Status` lines in the implementation plan, do not invalidate confirmation; any other content edit does.
7. **Batch only on explicit request.** This is the only exception to gates 1 and 2. If the user explicitly asks to review several documents together, still run discovery for each document in order, then present the drafts in one message and ask for a decision on each. A blanket acceptance such as "all good" covers every document presented; a document not accepted stays awaiting confirmation. If feedback changes an earlier document, later documents that depend on the change return to draft even if accepted; the rest keep their confirmation. A batch may not span the mockup gate: it holds documents from 0–3 only, or from 4–6 and the implementation plan only. Do not batch unprompted; you may mention the option if the user asks to go faster.

## Start or resume

1. Inspect project instructions, existing `documentations/`, and supplied planning material. For an existing codebase, inspect its structure, dependencies, and behavior. Never write a new product's artifacts into the skill repository; ask for a project path only when the target is unclear.
2. Read the progress record and resume at the earliest stage that is incomplete or unconfirmed according to its exit criteria. File existence alone is not completion. Reuse confirmation and mockup approval for unchanged reviewed content, checking the fingerprint when one was recorded. If a document changed after its confirmation, or confirmation is missing, present it for review: preserve the user's edits instead of regenerating the document or inventing acceptance.
3. If technical documents exist but the mockup or its approval is missing, complete the mockup gate before advancing. Preserve the technical content and mark affected sections for reconciliation.
4. Extract previous answers and decisions. If the product has not been described, begin with the equivalent of: "Who has what problem, and how should this product help them solve it?" Otherwise summarize what is known and ask about the most consequential gap.
5. Early in discovery, establish how end users will reach the product (website/web app, installed mobile app, desktop app, another interface, or a combination), the target devices/OS, and which platform comes first. Explain to the user that a website used on a phone and an installed mobile app are different delivery choices. Do not infer the answer from the word "app" or ask for a framework yet. If the user is unsure, explain the practical options and help them choose; keep the decision open until answered or explicitly delegated.

## Interview loop

For each document, including the implementation plan:

1. **Use what is known.** Extract previous answers, supplied material, and inspected facts. Do not re-ask settled questions or ask for facts you can inspect. Existing code shows current behavior, not necessarily the desired behavior or its reasons.
2. **Ask focused questions.** Default to one question; group at most three closely related ones. This limits a turn, not the interview: use as many rounds as the stage needs. Start open-ended, with the user's experience and reasoning; offer neutral choices and plain-language tradeoffs when they help the user express a preference. Do not lead with your recommendation before you understand that preference.
3. **Wait for the answer.** Do not answer on the user's behalf or treat silence as agreement. Meanwhile, continue independent research or drafting within the current document. Before yielding, save the pending question and resume point in the progress record. Any question tool or plain conversation works.
4. **Draft, check, then pass the [review gates](#review-gates).** Check the stage's exit criteria and resolve any remaining material question before presenting the document as ready. After the implementation plan is confirmed, run the [completion checks](#completion-and-handoff).

Interview for intent, not to fill a template:

- Prefer depth over fewer questions or speed. A feature list or a draft-confirmation question does not replace discovery. Before presenting a document as ready, understand the relevant motivations, concrete usage, priorities, and constraints through actual answers or explicit prior material.
- Ask for a recent real example: what triggered the need, what the person did, where it became difficult, and what outcome they wanted. Separate the user's own experience from hypotheses about other end users; do not turn anecdotes into research evidence.
- Probe vague answers such as "simple," "convenient," or "like that app": what that means in a specific situation, which aspect matters, what must differ. Follow the answer rather than a checklist.
- Ask why a requested feature matters and what would happen without it. Where relevant, explore first use, frequency, failure and recovery, and what the user would give up if time or budget forced a choice.
- Briefly reflect important answers back in plain language, and invite correction when an interpretation is uncertain. Treat contradictions as a reason to ask. Do not turn a short answer or silence into agreement with extra behavior you proposed.
- Treat "I don't know" as a cue for explanation, examples, and a follow-up question, not as delegation.
- End a stage's discovery when its intent is clear, not after a fixed number of questions. Skip irrelevant topics and respect a request to shorten the interview.

## Decisions and assumptions

- **Confirmed:** grounded in the user's answers, explicit constraints, or verified existing behavior. Keep user statements and inspected facts distinct from your proposals.
- **Assumed:** only for explicitly delegated choices, or minor technical/editorial details that do not decide product behavior or end-user experience. Reversibility alone is not a reason to decide for the user. Record the rationale, impact, and when to check it. Never invent user research, market numbers, or performance evidence.
- **Open:** ask when core end users, the problem, MVP boundaries, important permissions/data requirements, or architectural constraints are missing or conflict. Drafts are allowed, but do not finalize dependent designs or tasks.

Leave product behavior and experience choices open until the user answers or explicitly delegates them. Within a delegation, choose reasonable defaults and record the rationale and assumptions. Do not silently discard conflicting requirements.

Keep every required file even when the product has no frontend or backend: briefly explain what does not apply and describe the actual UI, CLI, storage, or service boundary. Do not add servers, authentication, payment, or external services just to fill a document.

## Technology stack

Decide the stack with the user, not for them, once the delivery platform and needs are understood. The discussion can begin in earlier interviews; it is finalized in `4_techspec.md`.

- Before proposing anything, understand the user's technical experience, existing code and services, budget, schedule, who will operate and maintain the product, and their preferences. Do not make a nontechnical user choose frameworks first or quiz them about unfamiliar ones.
- Explain the proposal (client, backend, starter, UI foundation) in terms of the user's goals, covering only material tradeoffs: supported OS, installation/distribution, native-device access, offline behavior, search visibility, delivery effort, recurring cost, operating burden. Compare alternatives only when they would change the decision.
- Invite the user's preference and concerns, and follow up on their reasons. After your explanation, the user can choose by consequences or explicitly delegate; unfamiliarity or silence is not delegation.
- Existing code, already-chosen technology, and explicit project requirements override the defaults below. Planning is not an unrequested migration, and a confirmed choice is not reopened.
- Check official documentation for decisions that depend on current library/API support or versions, and cite it. If verification is unavailable, record the gap.

Default proposals are starting points for that discussion, never a project's confirmed choice:

- **Web:** Next.js + Supabase, starting from a Vercel starter with shadcn/ui as the UI foundation. Define only the Supabase responsibilities the product needs; the default adds no authentication, storage, or other features to scope.
- **Installed mobile app:** establish the target operating systems and native-device needs first. Propose Swift for an Apple-only native app and React Native for a shared iOS/Android app; never silently pick Swift for an Android requirement. For React Native, propose Ignite as the starter unless a concrete constraint justifies an exception, and evaluate React Native Reusables for UI components. For Swift, propose Xcode's SwiftUI App template, native controls, and Apple design guidance. When the user delegates the choice, choose within these options and record the rationale.
- **App backend:** the app defaults cover the client only. Determine backend needs separately; Supabase is not automatically required.
- **Desktop or other interfaces:** derive the stack from the requirements instead of extending the web/mobile defaults.

Once the platform and MVP scope are clear, search for starters, UI templates, and design-system foundations without waiting to be asked, following [references/template-research.md](references/template-research.md): visual references and a compact design system before the mockup, starter fit in the tech spec after approval, setup and adaptation in the implementation plan. Research never bypasses the mockup gate or starts production work.

Carry the delivery platform, target devices/OS, and platform priority through every later document and the mockup. Record the agreed stack and the user's confirmation or delegation in the tech spec as the document guide describes, keeping unresolved choices visibly open. The mockup need not run on the production stack.

## Progress record

Keep the progress record as the last section of `0_one_pager.md`. If the one-pager does not exist yet, create it with only this section and draft the one-pager above it. If an equivalent record already exists, rename its heading to `## Planning progress` and move it to the end of the file. Do not create a separate state system. Use this shape:

```markdown
## Planning progress

| Artifact | Status | Rev | Fingerprint | Confirmed | Evidence |
| --- | --- | --- | --- | --- | --- |
| 0_one_pager.md | complete | 2 | 3f9a1c0b7d2e | 2026-10-22 | "좋아요, 다음으로 가죠" ("Good, let's move on") |
| … | | | | | |
| 3_screen_list_and_user_flows.md | complete | 1 | 8b04e6d2a915 | 2026-10-24 | "이대로 진행해요" ("Go ahead as is") |
| mockups/index.html | awaiting approval | M1 | — | — | — |
| 4_techspec.md | not started | — | — | — | — |

**Decisions**
- D-001 (confirmed 2026-10-22, user answer): Web app first; phone browsers must work. Affects 0_one_pager.md, 1_product_requirements_documentation.md.
- D-002 (assumed, delegated): … Check in TASK-004.
- D-003 (open): … Affects 4_techspec.md.

**Pending question:** …
**Resume point:** Waiting for approval of mockup M1.
**Unresolved mockup feedback:** none.
```

- **Rows:** one per artifact in the deliverables list. Document statuses are not started, draft, awaiting confirmation, complete, and needs revision; mockup statuses are listed in [references/mockup-review.md](references/mockup-review.md#required-user-decision). `Rev` is an integer for documents and `M1`, `M2`, … for the mockup; it increments each time you present changed content. Document 3 is complete once confirmed; its mockup row tracks the approval gate.
- **Evidence:** quote the user's acceptance with an English gloss, or give a message reference.
- **Fingerprint:** when a shell is available, record a hash at each confirmation or approval, running these commands from the project root. For a document, hash the content above its bookkeeping section, ignoring blank lines:
  `awk '/^## (Planning progress|Mockup review record)[[:space:]]*$/{exit} NF' FILE | shasum -a 256 | cut -c1-12`
  For `implementation_plan.md`, replace `NF` with `NF && !/^- Status:/` so TASK status updates do not count. For the mockup, hash every non-hidden file under `mockups/`:
  `find documentations/mockups -type f ! -name '.*' -print0 | sort -z | xargs -0 cat | shasum -a 256 | cut -c1-12`
  Where `shasum` is missing, replace `shasum -a 256` with `sha256sum`. The result `e3b0c44298fc` is the hash of empty input: nothing was read, so fix the path. On resume, a different hash means the artifact changed after review; in a git repository, `git diff` shows what changed. Without a shell, rely on `Rev` and say that later edits cannot be detected.
- **Decisions:** this list is an index. Each decision also appears in, or is linked from, the document it affects, where it is reviewed. Note the affected artifacts and keep proposed stack options separate from confirmed choices. When a decision changes, mark the old entry `superseded by D-00N` instead of deleting it, so the latest decision is clear.
- **Pending question and resume point:** clear the question once its answer is incorporated.

A document is complete when it meets its stage exit criteria, is consistent with the other artifacts, and has current confirmation.

### When decisions change

Mark affected documents `needs revision` and update them one at a time in upstream order, each through the review gates. Apply the latest user answer and record the reason. If it conflicts with an actual code or external constraint, explain the constraint and ask for a decision. Preserve unrelated edits and completion states. If a change alters approved screens, interactions, or flows, mark the mockup approval outdated, revise the mockup, and obtain approval of the new revision before advancing dependent technical work.

## Completion and handoff

Before claiming completion, reread all eight Markdown documents and inspect the mockup and its review record.

- All files are in the required locations, meet their stage exit criteria, and have current confirmation, including the implementation plan.
- Scope, terms, permissions, data, screens/interfaces, and technology choices agree.
- The current mockup revision is approved, and the screens and flows in the technical design match it.
- Every MVP requirement connects to a story, an actual user-facing surface, a design, an implementation task, and a verification method. Explain inapplicable mappings; do not invent features to fill gaps.
- Tasks identify files/modules, prerequisites, observable acceptance criteria, and verification. Mark proposed paths when no code exists yet.
- Tasks blocked by consequential open decisions are marked blocked. Do not declare the plan implementation-ready while blockers or mockup approval remain unresolved; return to the relevant question. Low-impact assumptions may connect to an initial validation task.

Check relative links and reference IDs. The final response links all eight documents and the approved mockup, lists remaining assumptions and open decisions, and provides a short execution prompt for the next AI. That prompt tells it to read `documentations/implementation_plan.md`, follow task dependencies, verify results, and record progress in each TASK's `Status` line. Status-only changes do not reopen the plan's review. Do not claim implementation or tests passed when only documentation and mockups were produced.
