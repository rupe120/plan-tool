---
title: Chat Deep Linking (with-frontmatter fixture)
status: planning
priority: medium
steps:
  - id: 1
    title: Placeholder step (frontmatter content is irrelevant to parse_source)
---

# Implementation Plan: Chat Deep Linking Integration

**Document Version**: 2.0 (split into summary + detail set)
**Created**: 2026-03-27
**Last Restructured**: 2026-05-12
**Status**: Planning
**Priority**: Medium
**Estimated Effort**: 2–3 weeks (phased)

---

> **Summary plan.** This document is the high-level overview. Full execution detail (resolver code, route map, system-prompt instructions, post-processor, test tables, rollout playbook) has been split into a companion detail set so this file fits within the plan-tool `--from-existing` byte budget.
>
> **Detail set**: [`plan-details/chat-deep-linking/`](./plan-details/chat-deep-linking/README.md)

---

## Overview

Enable the AI chat agent to include deep links within its responses that navigate users directly to specific screens within the web and mobile apps. When the AI coach mentions assessments, mentors, opportunities, profile sections, or other in-app features, those references should be tappable/clickable links that take the user to the relevant screen — eliminating friction and turning the chat into an active navigation hub.

**Goal**: AI responses containing references to in-app features render as actionable deep links on both web and mobile, with a consistent UX and graceful fallback for unknown routes.

**User Story**: As a platform user, I want the AI Coach to recommend and link me directly to relevant platform features (assessments, mentorship, tuition assistance, opportunities), so that I can take immediate action on career guidance without navigating manually.

**Owner**: Product owner — **Buyer**: Business stakeholder

### Acceptance Criteria

- Given the AI Coach generates a recommendation, when it references an assessment, mentorship, Vendor program, or opportunity, then a deep link to that feature is surfaced in the response.
- Given a user taps/clicks a deep link from the AI Coach, when they are navigated, then they land on the correct destination on mobile (iOS/Android) and web.
- Given a user makes progress in another feature of the app (e.g. Vendor programs, Assessments) or provides new information within the chat about a skill or experience, their profile data is updated, then subsequent recommendations reflect that data.

### Technical Requirements

- Enable link building for known application paths for relevant AI chat agent results and include them in the response.
- All deep links must carry an indication of where they were built so usage can be tracked.
- After completing an assessment identified in the AI summary produced by the background process, the background process summary then reflects the fact that the assessment was taken.

---

## Approach at a Glance

Define a custom `app://` URI scheme that the AI agent emits inside standard markdown links. Both the web and mobile markdown renderers intercept `app://` links and route in-app via a **shared resolver** that maps each URI to a platform-specific path. External URLs (`https://…`) keep their existing behavior. A regex post-processor injects links into AdviceService responses we don't control.

```markdown
You can update your skills in your [profile](app://profile) or try the
[career assessment](app://assessments/assessment-service).
```

Full route map and gap analysis: [`plan-details/chat-deep-linking/01-current-state-and-routes.md`](./plan-details/chat-deep-linking/01-current-state-and-routes.md).

---

## Implementation Phases

### Phase 1 — Link Resolution Infrastructure (week 1)

Land the plumbing so the apps can recognize `app://` markdown links and route in-app. No user-visible change yet.

- Create shared resolver `packages/shared/src/utils/deep-link-resolver.ts` exporting `resolveAppLink` and `isAppLink`.
- Web: override `ReactMarkdown` `components.a` in `ChatScreenStyled.tsx` to intercept `app://` and call `useNavigate`.
- Mobile: pass an `onLinkPress` handler to `react-native-markdown-display` in `aiChat/[id].tsx` that routes via `expo-router`.

Full code samples and rationale: [`plan-details/chat-deep-linking/02-link-resolution-infrastructure.md`](./plan-details/chat-deep-linking/02-link-resolution-infrastructure.md).

### Phase 2 — AI Agent Integration (week 1–2)

Make the agent emit `app://` links naturally, and inject them into AdviceService output via regex.

- Add a **DEEP LINKS** section to the system prompt in `amplify/bedrock/chat-agent/agent.py` listing the available link surface and usage rules (max 2 per message, natural anchor text, only actionable references).
- Add `injectDeepLinks(text)` in `amplify/lambda/ai-chat-invoke/handler.ts` to post-process AdviceService responses with feature-phrase regexes. Skips when text already contains `app://`. Capped at 2 injected links.

Full prompt text + regex pipeline: [`plan-details/chat-deep-linking/03-ai-agent-integration.md`](./plan-details/chat-deep-linking/03-ai-agent-integration.md).

### Phase 3 — Testing & Polish (week 2–3)

- Unit tests for `deep-link-resolver.ts` covering exact routes, dynamic segments, query params, unknown-route fallback, and non-`app://` URIs.
- Web integration tests for the markdown override (`navigate` call, external-link behavior, malformed-link fallback).
- Mobile manual / Detox verification of in-app routing and back-stack behavior.
- Agent prompt verification table run against the dev sandbox.

Full test tables, manual checklist, and coverage targets: [`plan-details/chat-deep-linking/04-testing-and-verification.md`](./plan-details/chat-deep-linking/04-testing-and-verification.md).

---

## Critical Files

| File                                                             | Action     | Description                                                                    |
| ---------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------ |
| `packages/shared/src/utils/deep-link-resolver.ts`                | **Create** | Shared `app://` URI resolver with route map                                    |
| `packages/shared/src/index.ts`                                   | **Modify** | Export `resolveAppLink`, `isAppLink`                                           |
| `apps/web/src/shared/components/ChatScreenStyled.tsx`            | **Modify** | Custom `components` prop on `ReactMarkdown` for `app://` link interception     |
| `apps/mobile/app/aiChat/[id].tsx`                                | **Modify** | `onLinkPress` handler on `Markdown` for `app://` navigation                    |
| `amplify/bedrock/chat-agent/agent.py`                            | **Modify** | DEEP LINKS section in the system prompt                                        |
| `amplify/lambda/ai-chat-invoke/handler.ts`                       | **Modify** | `injectDeepLinks()` post-processing for AdviceService responses                |
| `packages/shared/src/utils/__tests__/deep-link-resolver.test.ts` | **Create** | Unit tests for deep link resolution                                            |

---

## Verification & Rollout Summary

- **Phase 1 → infrastructure**: no behavioral change; safe to promote through environments.
- **Phase 2 → agent prompt**: deploy to dev sandbox first, conversation-test, tune for over-linking before promoting.
- **Phase 3 → post-processor**: deploy after the prompt is stable; monitor for false positives.
- **Production**: QA → staging → prod, with a one-week link-density review window.

Full rollout playbook, design trade-offs, and future-work backlog: [`plan-details/chat-deep-linking/05-rollout-tradeoffs-and-future.md`](./plan-details/chat-deep-linking/05-rollout-tradeoffs-and-future.md).

---

## Success Criteria

- [ ] AI responses reference in-app features as clickable deep links.
- [ ] Deep links navigate correctly on both web and mobile.
- [ ] External URLs continue to work normally.
- [ ] No regression in chat message rendering performance.
- [ ] Deep link resolver has > 90% unit test coverage.
- [ ] AI agent includes links naturally without over-linking (≤ 2 per message in ≥ 95% of responses).

---

## Detail Documents

The full execution-level content is preserved in the companion folder:

1. [Current State, Gap Analysis, and Supported Routes](./plan-details/chat-deep-linking/01-current-state-and-routes.md)
2. [Phase 1 — Link Resolution Infrastructure](./plan-details/chat-deep-linking/02-link-resolution-infrastructure.md)
3. [Phase 2 — AI Agent Integration](./plan-details/chat-deep-linking/03-ai-agent-integration.md)
4. [Phase 3 — Testing and Verification](./plan-details/chat-deep-linking/04-testing-and-verification.md)
5. [Rollout, Trade-offs, and Future Enhancements](./plan-details/chat-deep-linking/05-rollout-tradeoffs-and-future.md)

---

## References

- [React Markdown custom components](https://github.com/remarkjs/react-markdown#components)
- [Expo Router linking](https://docs.expo.dev/router/advanced/linking/)
- [react-native-markdown-display onLinkPress](https://github.com/iamacup/react-native-markdown-display#rules)
- [AI Chat Response Time Optimization](2-ai-chat-response-time-optimization.md) — related chat pipeline plan
- [AI Chat Conversational Tone](2-ai-chat-conversational-tone.md) — related prompt engineering plan
