# Mockup creation and approval

Create the mockup after the user confirms `3_screen_list_and_user_flows.md` and before technical specification. The purpose is to let the user assess the actual layout and journey before those choices become architecture and implementation tasks. Confirmation of the screen/flow document does not approve an unseen mockup.

## Build a concrete artifact

1. Read the one-pager, PRD, stories, and screen/flow document. Follow the product's audience, platform, existing design system, and any supplied visual references. Search the preferred template/design-system sources in [template-research.md](template-research.md), establish the product's tokens and component states, and adapt useful findings to the actual MVP. Reuse an available frontend design skill when compatible, following [skill-options.md](skill-options.md).
2. Default to a self-contained `documentations/mockups/index.html` with embedded CSS and minimal JavaScript. A multipage mockup may link additional local files in this directory. Use local/system fonts and sample data; require no package installation, remote service, or production credentials to review it. For an existing project, a framework preview is also suitable when already available and easier to inspect.
3. Draw every MVP screen in the inventory and the meaningful states needed to review its journey. Give screens stable SC IDs and linkable anchors. Include the core happy path and consequential empty/error/permission/confirmation states. A labeled state selector can expose alternate states without implementing a backend.
4. Make primary navigation and the critical user flow demonstrable with sample data. Real saving, authentication, payment, and external integrations are outside a mockup's scope. Keep preview controls and sample-data labels separate from product copy.
5. Match the confirmed delivery platform and target devices/OS. Demonstrate both narrow and wide layouts for a responsive web product; for an installed mobile or desktop app, use the intended screen/window sizes and relevant navigation conventions. An HTML preview may represent an installed app without changing the product into a website. For multiple MVP platforms, show the consequential layout and interaction differences. Use readable hierarchy, real domain labels, visible keyboard focus, and actionable error/empty states. Do not add features merely to make the design look complete.
6. For a CLI/API-only product, preview the actual terminal interaction or request/response journey in the same reviewable artifact. Do not invent an unrelated graphical interface. The user still reviews and approves the intended interaction.

An ASCII sketch or flowchart can support exploration, but does not replace the reviewable mockup. Do not create production application code to satisfy this stage.

## Inspect before presenting

- Open the artifact in an available browser/preview and inspect its rendered layout and main interactions. Check the inventory against SC IDs and test the primary journey.
- Capture and inspect screenshots when supported, saving them outside `documentations/mockups/` so they do not change the mockup's fingerprint. Follow applicable project visual review instructions on each iteration; an available visual-verdict skill can help inspect screenshots. Automated visual checks assess quality; they do not grant user approval.
- Fix broken navigation, clipped content, missing key states, and mismatches with the requirements before requesting approval. If rendering is unavailable, give the direct HTML artifact link and clearly state which visual/interaction checks remain unverified. Never claim to have opened or reviewed an artifact that was not inspected.
- Record the revision, artifact links, covered screens/states, inspection evidence, and the visual/template sources and attribution actually used in the `## Mockup review record` section at the end of document 3. Keep the concise review status in the one-pager's progress record. Both are bookkeeping and do not reopen document review.

## Required user decision

Use a simple revision identifier such as `M1`, incrementing when the presented design changes. Track one of: not started, draft, awaiting approval, changes requested, approved, or outdated.

Present the actual mockup link or preview, name the revision, briefly explain the main journey, and ask a single concrete question equivalent to:

> Please review mockup M1: [artifact]. Do you approve this version's screens and flow, or what should change?

Wait for the user's response. What counts as approval follows the [review gates](../SKILL.md#review-gates): an unambiguous acceptance of the presented revision, never a delegation, silence, or an automated check.

- **Approval:** Record the revision, artifact, fingerprint (when a shell is available), and the user's actual acceptance message or available message reference. Then continue with `4_techspec.md` under the review gates. Do not ask again for unchanged approved mockups.
- **Changes requested:** Record the feedback, revise the affected screens, inspect the new revision, and present it for approval again. If document 3's content changes too, follow gate 5 of the [review gates](../SKILL.md#review-gates) and ask one question such as "Do you approve mockup M2 and the matching changes to document 3, or what should change?" Do not advance dependent technical work while review is pending.
- **Ambiguous feedback:** Ask whether the presented version is accepted, explaining the specific unresolved point. Do not infer acceptance.
- **Later design changes:** Mark affected approval outdated and downstream sections as needing revision. Update the mockup, explain the change, and obtain approval for the new revision before advancing dependent technical work. Preserve unaffected decisions and artifacts.

