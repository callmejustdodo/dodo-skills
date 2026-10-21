# Template discovery and selection

Search during each product planning engagement once its platform and MVP scope are known. Start from the preferred sources below and adapt the search to the actual product. Reuse already-verified findings on resume unless the requirements changed or freshness matters. Source pages were checked on 2026-10-18; revisit current documentation and selected revisions rather than treating this snapshot as a permanent compatibility guarantee.

## Preferred starter and template sources

| Platform | Search sources | Selection policy |
| --- | --- | --- |
| Next.js web | [Vercel Next.js templates](https://vercel.com/templates/next.js), especially the [Supabase Starter](https://vercel.com/templates/next.js/supabase) | Search here first. The Supabase Starter is a strong baseline for the default stack and includes Tailwind and shadcn/ui. Check the linked source repository; a catalog listing alone does not prove fit or maintenance. Remove features the MVP does not need; keep the starter's authentication only if the MVP requires it. |
| Next.js + Supabase integration | [Supabase Next.js quickstart](https://supabase.com/docs/guides/getting-started/quickstarts/nextjs) | Use the official integration example to verify or supplement a Vercel starter. Avoid introducing a second scaffold when the selected starter already covers the same setup. |
| React Native | [Infinite Red Ignite documentation](https://docs.infinite.red/ignite-cli/) and [source repository](https://github.com/infinitered/ignite) | Prefer Ignite for new React Native products. Check current Expo/React Native, navigation, theming, and dependency choices. Use another starter only for a concrete requirement or existing-project constraint; document the reason. Do not invent alternative candidates merely to fill a comparison table. |
| Swift / SwiftUI | [Xcode app-project templates](https://developer.apple.com/documentation/xcode/creating-an-xcode-project-for-an-app), [SwiftUI resources](https://developer.apple.com/swiftui/resources/), [SwiftUI tutorials](https://developer.apple.com/tutorials/swiftui/), and [Apple sample code](https://developer.apple.com/documentation/samplecode/) | Default to Xcode's SwiftUI App template and add focused official examples for required features. These are scaffolding and learning/sample sources, not a complete production boilerplate. Adopt a third-party all-in-one starter only when its verified benefit justifies its dependencies and maintenance burden. |

If these sources do not cover the product, search original publisher sites and GitHub repositories using the chosen stack plus the actual product/use case. Preserve the platform and stack preferences when expanding the search. Do not interpret a Vercel template listing as a requirement to deploy to Vercel.

## Preferred design-system and component sources

| Platform | Sources | How to use them |
| --- | --- | --- |
| Web | [shadcn/ui documentation](https://ui.shadcn.com/docs), [Blocks](https://ui.shadcn.com/blocks), and [Theming](https://ui.shadcn.com/docs/theming) | Preferred foundation for new Next.js UI. Inspect source components, useful page blocks, and semantic theme tokens. Customize them to the product rather than copying an unrelated dashboard. Components are editable project code; define ownership and an update strategy. |
| React Native | [React Native Reusables](https://reactnativereusables.com/), [installation guide](https://reactnativereusables.com/docs/installation/manual), and [source repository](https://github.com/founded-labs/react-native-reusables) | Preferred candidate to evaluate for reusable native UI. Check the selected version's NativeWind/Uniwind styling path, primitives, theme, portal/provider, and bundler requirements. Use its existing-project integration guidance for Ignite rather than replacing Ignite with the Reusables starter. |
| Swift / SwiftUI | [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/), [Apple Design Resources](https://developer.apple.com/design/resources/), and [SwiftUI resources](https://developer.apple.com/swiftui/resources/) | Use native controls and platform interaction conventions as the foundation. Check target OS availability and resource usage terms; a design resource download is not automatically a code starter. |

Ignite has its own themed styles/components, while React Native Reusables introduces another styling setup. Do not assume they are integrated out of the box. Verify the selected versions, map tokens to one product theme, adapt provider/navigation examples to Ignite's actual structure, and avoid duplicate component systems. Plan a small integration check for a representative screen, overlay, and theme behavior before broad adoption. If the combination is unsuitable, explain the concrete issue and keep Ignite's components/theme as the fallback; do not silently replace the preferred starter. shadcn/ui web components are not directly interchangeable with React Native or SwiftUI controls.

Before mockups, record a compact design-system direction in document 3: chosen foundation, semantic colors, typography, spacing, radii, required component variants/states, and relevant accessibility/platform conventions. Include dark mode only when in scope. Use this same direction in the mockup and map it to implementation tokens/components in document 5 after approval. An HTML mockup may represent native controls without installing the production UI stack; record that it demonstrates intended appearance and flow rather than proving native integration.

## Search at the relevant stage

- **Before mockups:** Look for useful UI templates, screen patterns, and visual references that match the product's audience, core journeys, and target devices. Keep the research notes in document 3. Inspiration does not require adopting a template's code or backend.
- **After mockup approval:** Confirm starter/boilerplate compatibility with the approved journeys and intended stack while writing document 4. Earlier research may identify code candidates, but does not finalize technical documents before approval.
- **Web:** Search for Next.js + Supabase starters and product-specific UI templates. A candidate using another backend is not automatically compatible with the default stack.
- **Apps:** Search for Swift or React Native starters appropriate to the selected client stack, target OS, and required device capabilities. Do not treat a web template as an app starter merely because it has a narrow layout.
- **Existing products:** Inspect existing scaffolding and the design system first. Search for compatible additions or references; replacing the project foundation needs a concrete reason within the requested scope.

Use available web search and browse the actual publisher/repository pages, starting from the preferred sources above. Search directories and marketplace listings help discovery but do not establish suitability. Keep the shortlist small, usually two or three credible candidates when alternatives are useful; stop when the evidence supports a choice. A compatible preferred starter may be proposed directly after inspection; discuss its fit with the user as part of the stack conversation, unless that project choice is already confirmed or the choice has been explicitly delegated. Do not pad the list with poor matches.

## Inspect before recommending

For shortlisted candidates, inspect original documentation, repository files, and demos where available. Record what was actually verified:

- Fit to required screens, user journeys, accessibility, and target devices.
- Framework/toolchain versions and dependencies, backend assumptions, and compatibility with the selected stack. Use current official documentation when compatibility needs verification.
- License, commercial-use/redistribution terms, attribution obligations, and price. Missing licensing is an unresolved reuse constraint, not permission to copy.
- Maintenance signals such as recent releases/commits, archived status, and relevant unresolved issues. Popularity alone does not prove quality or maintenance.
- Setup effort, required services, and the work to remove unused features and adapt the template to the MVP. Avoid templates whose extra systems outweigh the saved work.

Separate visual inspiration, reusable UI components, and an implementation starter in the findings. Do not claim code was run or a demo inspected unless it was. If search or source access is unavailable, record the limitation and use an original design/minimal scaffold with any consequential selection still open; do not invent candidates, licenses, or compatibility evidence.

## Decide and carry forward

Keep a compact comparison in the relevant existing document: candidate and direct source link, date checked, intended use, fit, license/cost, maintenance/compatibility evidence, adaptation effort, and decision. Include an original/minimal implementation option when no candidate offers a clear benefit.

Discuss the recommended stack, starter, and UI foundation with the user and include the agreed choice and rationale in the current document's required review. General stack preferences do not replace this project-specific conversation. Do not add a separate approval step for every search result. Ask during research when a material user decision remains, such as a paid purchase outside the agreed budget or a required departure from the selected stack. Keep within existing authority; search alone does not authorize buying, accepting new terms, deploying, or executing a downloaded starter's setup scripts. During planning, inspect source and adapt permitted UI material for the review mockup as useful; production setup belongs in implementation tasks.

- In document 3's `## Mockup review record`, cite the visual/template sources actually used in the mockup and note applicable attribution. The user approves the actual customized mockup, not an unseen marketplace demo.
- In document 4, record the selected implementation starter or the decision to use none, its verified source/version or revision when available, and the technical constraints it introduces. Resolve consequential licensing/compatibility gaps before marking template-dependent work ready.
- In frontend/backend architecture, identify retained, adapted, removed, and newly required parts where relevant. Template features do not become product requirements by default.
- In the implementation plan, include acquisition/setup, adaptation, removal of unused features, attribution, and verification tasks as applicable. Pin the selected source revision/version where possible and have the implementing AI recheck material compatibility or licensing changes before reuse.
