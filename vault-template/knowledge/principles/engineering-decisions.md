---
title: Right-sized engineering decisions
status: approved
tags: [architecture, maintainability, patterns, cross-stack]
verified_at: 2026-10-24
sources: []
---

# Right-sized engineering decisions

- Start from the project's documented rules, nearest similar code, and existing tests.
- Prefer understandable, cohesive code with clear dependency boundaries; don't multiply layers without a concrete need.
- Classes, composition, hooks, modules and functions are tools, not universal mandates.
- Validate user inputs at trust boundaries and preserve existing security controls.
- Introduce new libraries or major architecture patterns only with a clear benefit and compatibility plan.

This note is deliberately general; it does **not** override established safe project conventions. No framework-specific claims are made here.
