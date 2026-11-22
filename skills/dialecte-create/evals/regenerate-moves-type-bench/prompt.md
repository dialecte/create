---
tags: [dialecte]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write]
---

I regenerated the definition of my dialecte package (a new optional element in the schema) with @dialecte/create. The package pins @dialecte/cli 0.10.0 and lands through the merge queue; my change has a changelog fragment `changes/new-element.md`. CI's type-perf job now fails: `npm run type-bench:check` prints `coverage: surface  +6.1% over its base` and exits 1. The schema change is wanted and the extra cost is accepted. Do not run anything: write ./out/PLAN.md with what I change, the exact command lines, the files I touch, and what I must not do.
