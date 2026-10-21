# Document stage guide

Use the section for the current stage. These are content criteria, not a demand for identical length or empty boilerplate. Scale detail to the product and explain inapplicable items.

Every stage's exit requires both the content criteria below and the user's confirmation under the [review gates](../SKILL.md#review-gates). Having enough information is not confirmation. Document 3 is confirmed before the mockup is built; the mockup then has its own approval gate.

## Interview focus by stage

Explore the relevant topics through follow-up questions across multiple turns. These are prompts for understanding, not a questionnaire to send all at once or a reason to repeat settled answers. Document confirmation does not replace this interview.

| Stage | Intent to understand before drafting a review-ready document |
| --- | --- |
| One-pager | Why this product now; who first needs it; a recent problem episode; current workaround and its shortcomings; desired change; first-release boundaries and platform. |
| PRD | Why each core capability matters; what is essential versus negotiable; business rules, permissions, and data expectations; what success and unacceptable failure look like. |
| User stories | A concrete start-to-finish usage example; the actor's context and information; decisions they make; what happens after success, interruption, or failure. |
| Screens and flows | What someone should see and do first; information/action priority; preferred interaction patterns and examples they like or dislike, with reasons; important device and accessibility needs. |
| Technical specification | Discuss the development stack together: existing technology and skills, the user's preferences, suitable options, and reasons for the choice. Explore privacy, offline/connectivity, integrations, scale expectations, budget, and who operates it. Explain relevant tradeoffs through consequences the user understands; obtain their choice or explicit delegation. |
| Frontend architecture | UI expectations not yet settled: cross-device consistency, navigation/state restoration, interaction behavior, and accessibility priorities. Derive internal module choices from confirmed needs. |
| Backend architecture | Data ownership, sharing, retention/deletion, recovery, and operational responsibilities where unresolved. Do not invent policies to finish the architecture. |
| Implementation plan | Which usable outcome should arrive first; priorities when scope competes with deadline/budget; release constraints; who will validate the result and how. |

Use stable IDs such as `FR-001` for requirements, `US-001` for stories, `SC-001` for screens, and `TASK-001` for implementation tasks. Preserve an existing ID scheme. Give API, CLI, or batch surfaces referenceable names when needed. Connect artifacts through relative links and IDs; do not reuse a retired ID for a different meaning.

## 0_one_pager.md — Why and for whom

Include:

- Product in one sentence, core end user, problem, and current workaround.
- Proposed solution and the change it should create for end users.
- Core MVP value, included scope, and excluded scope.
- Success signals and measurement methods; distinguish goals and assumptions from evidence.
- Delivery format (website/web app, installed mobile app, desktop app, or other interface), target devices/OS, and first-release platform priority. Distinguish mobile browser use from an installed app.
- Known schedule, budget, operating constraints, significant risks, and open decisions.
- A final `## Planning progress` section in the [progress record](../SKILL.md#progress-record) format. It is bookkeeping and not part of the document's reviewed content.

Ask when needed: "Who will use this first?", "If the first version does only one thing well, what should it be?", or "Will people use this in a browser, install it on their phone or computer, or use another interface?"

Exit: The end users, problem, value, MVP boundary, and delivery platform are clear. Resolve the platform through the user's answer or explicit delegation before finalizing platform-dependent designs; do not fabricate market evidence.

## 1_product_requirements_documentation.md — Required behavior

Include:

- Product goals and MVP boundaries, linked to the one-pager.
- Supported platforms/devices and relevant platform constraints, such as installation/distribution, offline behavior, or device permissions. Include only what the product needs.
- Functional requirements with ID, actor/trigger, expected behavior, priority, and observable acceptance criteria.
- Relevant roles/permissions, business rules, inputs/outputs, and data retention/deletion needs.
- Relevant nonfunctional requirements such as performance, accessibility, reliability, and security. Explain numerical targets or label assumptions.
- Exclusions, dependencies, and open decisions.

Ask when needed: "Who should be allowed to do this?" or "What can be left out of the first release?"

Exit: Every MVP requirement has acceptance criteria; required and later scope are distinct. Avoid prematurely fixing screen layouts or implementation details.

## 2_user_stories.md — User outcomes

Include:

- Role-specific stories with ID, linked FR IDs, and "As a [role], I want to [action] so that [outcome]."
- Priority, preconditions, and acceptance criteria for the normal scenario.
- Relevant failure, denied permission, cancellation, and retry scenarios.
- Given/When/Then criteria where they clarify a testable outcome. Split stories that bundle independent end-user goals; keep engineering work as technical tasks.

Ask when needed: "What information does the end user already have when starting?" or "Where should the end user return after a failure?"

Exit: Stories explain all MVP functionality and make success testable. Nonfunctional requirements may connect directly to technical verification tasks.

## 3_screen_list_and_user_flows.md — Surfaces and journeys

Include:

- Screen inventory with SC ID, purpose, actor/permission, entry/exit paths, main actions, and related US/FR IDs.
- Required information, inputs, validation, and loading/empty/success/error states per screen.
- Main flows from entry condition through actions and branches to completion, using readable text or Mermaid.
- Relevant back navigation, interruption, reentry, access denial, and recovery paths.
- A compact visual direction and product design system: chosen component foundation, layout, typography, semantic colors, spacing, radii, component variants/states, and relevant accessibility/platform conventions. Consult the preferred design-system sources in [template-research.md](template-research.md). Interview the user about the intended feel and interaction priorities, using concrete references and asking what they like or dislike and why. Translate those answers into a coherent direction; use agent-chosen visual defaults only within explicit delegation.
- UI template/reference research and sources used for the mockup, following [template-research.md](template-research.md).
- For products without screens, actual CLI/API/batch surfaces and their usage flows instead of invented GUI screens.
- After the document is confirmed, a final `## Mockup review record` section: a coverage table mapping SC IDs and important states to links under `mockups/`, the current revision, review status, inspection evidence, and the visual/template sources and attribution actually used. It is bookkeeping and not part of the document's reviewed content.

Ask when needed: "What should someone do first on arrival?" or "What should happen after completing this flow?"

Exit: Every core story has an entry-to-completion path with necessary states and exceptions. Once confirmed, document 3 is complete; then create the mockup and complete the approval gate in [mockup-review.md](mockup-review.md) before advancing to document 4. A text flow or Mermaid diagram alone is not a mockup.

## 4_techspec.md — System contracts

Include:

- Confirmed platforms, existing code, external constraints, and technology choices discussed with the user. Use the default proposals in [technology stack](../SKILL.md#technology-stack) as a discussion starting point. Record the agreed client/backend stack, starter, and UI foundation, rationale, material tradeoffs, and actual user confirmation or explicit delegation; distinguish the mobile client choice from its backend needs. Record alternatives for consequential decisions only.
- Starter/boilerplate comparison and selection (or the reason to use none), with source links, checked date, license/cost, compatibility evidence, and adaptation needs from [template-research.md](template-research.md).
- System responsibilities and data flow, aligned with the approved mockup revision.
- Data model: fields, types, identifiers, relationships, required values, and important invariants.
- Relevant API/CLI/internal interface contracts: inputs, outputs, validation, authentication/authorization, and errors.
- Date/timezone handling, duplicate processing, or concurrency rules where they affect behavior.
- Test scope, runtime/configuration, and necessary deployment/operating constraints.
- Consequential technical assumptions and their verification methods. Do not record secrets.

Ask when needed: "What technology or integrations must we keep?" or "Who can operate the deployed system?" After explaining a suitable stack and its consequences, ask what the user thinks and what concerns them; do not present the default as already decided.

Exit: Core contracts are specific enough that implementers agree on data and interfaces. Vague promises such as "fast" or "scalable" are insufficient. The development stack has been discussed and the choice confirmed or explicitly delegated; material choices are resolved. User approval of the current mockup is recorded.

## 5_frontend_architecture.md — UI structure

Include:

- Existing or proposed directories/modules; routes/screens mapped to SC IDs and approved mockup states.
- Layout/component responsibilities, implementation token mappings for the approved product design system, state ownership, and remote/local data boundaries. Record starter/UI integration needs, including Ignite and React Native Reusables compatibility checks when selected.
- Interface integration, form validation, loading/errors, and access denial.
- Applicable responsive/accessibility requirements and test boundaries.
- References to technical contracts instead of redefining the same API differently.

Exit: Each MVP screen or user surface has an implementation location, data flow, and state handling consistent with approved mockups. If there is no UI, explain that and describe the actual user-facing boundary.

## 6_backend_architecture.md — Data and business rules

Include:

- Existing or proposed directories/modules; endpoints/jobs linked to requirements.
- Request handling, business rules, and data access responsibilities. Avoid unnecessary layers for a small product.
- Relevant authentication/authorization, validation, transactions, duplicate processing, and error handling.
- Storage/migrations, external integrations, asynchronous work, and recovery only where needed.
- Necessary logging, monitoring, deployment, configuration, and test boundaries.

Exit: The location enforcing important invariants and permissions is clear. If there is no separate backend, explain that and describe local storage or external service boundaries.

## implementation_plan.md — Work for the next AI

Read and reconcile the seven preceding documents and approved mockups first. This stage does not invent new features or contracts.

Include:

- Goal, document reading order and relative links, approved mockup revision/link, current code state, and exclusions.
- A dependency order that delivers a minimal working user flow early. Mark parallel work only when shared-file conflicts are absent.
- Each task includes the following information.

```markdown
### TASK-001: [Observable outcome]
- Status: pending / in progress / blocked / complete
- References: FR/US/SC IDs or technical requirement, document links, relevant mockup state
- Prerequisites: none or TASK IDs
- Change locations: existing files/modules or explicitly proposed paths
- Work: inputs, behavior, outputs, and relevant error handling
- Interfaces: names/types consumed from or produced for related tasks, where needed
- Acceptance criteria: observable results
- Verification: verified commands or concrete manual scenarios with expected results
- Blockers/assumptions: omit if none; otherwise include resolution or initial validation task
```

- A traceability table: MVP requirement → story/surface → approved mockup where applicable → design → TASK → verification. Repair missing coverage and remove unsupported work.
- Integration checks for core journeys, relevant permission/error paths, actual lint/typecheck/test/build commands, and necessary manual checks.
- Mark nonexistent commands as proposals to add during implementation. Do not present unrun commands or tests as verification evidence.
- Execution instructions: read the source documents, follow dependencies, verify before completing tasks, and record results. Update affected documentation when contracts change. Ask about consequential unresolved user decisions; revisit mockup approval when a change alters the approved design.

Exit: Another AI can start without the chat history, success is decidable per task, consequential blockers are resolved, and the mockup approval is current. Include schedule estimates only when requested or supported.
