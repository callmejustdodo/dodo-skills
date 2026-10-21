# Optional skills for this workflow

These candidates were inspected on 2026-10-16. They are optional sources of specialized methods, not required dependencies. Discover installed capabilities before using one, read its current instructions, and confirm its workflow fits the requested stage. Do not automatically install or execute packages found in search results.

This skill owns the document paths, sequence, interview progress, per-document confirmation, and mockup approval gate. If invoking another skill would introduce an incompatible lifecycle, output path, question policy, or execution requirement, use this workflow's built-in stage guidance instead. Do not invoke another skill and then silently skip its mandatory instructions.

## Candidate mapping

| Stage | Candidate and inspected source | Useful contribution | Fit considerations |
| --- | --- | --- | --- |
| Discovery and one-pager | [mattpocock/skills: grilling](https://github.com/mattpocock/skills/blob/main/skills/productivity/grilling/SKILL.md), also exposed through `grill-me` | Ask decisions in dependency order; obtain facts from the environment rather than asking the user to look them up. | The inspected `grill-me` is a wrapper that calls `grilling`. The latter asks the entire available question frontier and requires confirmation at closure. Treat it as a reference when its full interview would conflict with this workflow's focused questions and one-document-at-a-time reviews. |
| PRD | [github/awesome-copilot: prd](https://github.com/github/awesome-copilot/blob/main/skills/prd/SKILL.md) | Discover problem, success measures, and constraints; clarify exclusions and acceptance criteria. | Its fixed minimum question count and combined PRD schema differ from this workflow's reuse of known answers and separate documents. Use the built-in PRD guide when these conflict; do not invent KPIs to fill a schema. |
| User stories | [deanpeters/Product-Manager-Skills: user-story](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/user-story/SKILL.md) | Connect a specific actor, action, and outcome with Given/When/Then acceptance scenarios. | Keep stable FR/US IDs and this workflow's output path. Engineering tasks should not be disguised as user stories. |
| Screens, mockups, frontend architecture | [anthropics/skills: frontend-design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md) | Establish a product-specific visual direction, consistent UI copy, and an inspected visual artifact. | Use it to produce the planning mockup; retain the explicit user approval gate. Mockup code is a review artifact, not permission to implement the production product. Respect the established product instead of inventing a new brief. |
| Implementation plan | [obra/superpowers: writing-plans](https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md) | Define file responsibilities, task interfaces, dependencies, and checkable verification steps. | Its default location, required execution skills, and execution handoff differ. Prefer the built-in implementation-plan guide unless the full workflow is compatible. Do not start implementation or require per-task commits solely because this candidate suggests them. |

## Already-installed planning workflows

When present, `deep-interview` and `plan` can provide useful interviewing, tradeoff, and verification methods. Their full OMX/OMC workflows may require state files, separate planning artifacts, runtime tools, approvals, or execution handoffs. They are not required stages of this skill. The `ralplan` shim is not a standalone interview helper. A separate consensus review is appropriate only when requested or justified by a consequential architecture decision.

## Optional installation commands

Use these only when installation is requested. These commands were discovered through the Skills CLI; reread the source and relevant dependencies before installing. Popularity and repository stars are discovery signals, not proof of compatibility or correctness.

```sh
npx skills add mattpocock/skills --skill grilling
npx skills add github/awesome-copilot --skill prd
npx skills add deanpeters/product-manager-skills --skill user-story
npx skills add anthropics/skills --skill frontend-design
npx skills add obra/superpowers --skill writing-plans
```

Discovery pages: [grill-me](https://skills.sh/mattpocock/skills/grill-me), [prd](https://skills.sh/github/awesome-copilot/prd), [user-story](https://skills.sh/deanpeters/product-manager-skills/user-story), [frontend-design](https://skills.sh/anthropics/skills/frontend-design), and [writing-plans](https://skills.sh/obra/superpowers/writing-plans). Registry snapshots may lag the repository; the source instructions govern compatibility.
