---
name: dialecte-__dialecteId__
description: Domain map of __packageName__, the __DialecteName__ dialecte built on @dialecte/core - which business verbs it already offers on doc.query and tx, what its hooks keep coherent on every write and import, and where new code goes in this package. Use it for any task that reads or writes __DialecteName__ documents through dialecte, in an app or inside this repository, even when the user only names an element of the schema. Load together with the dialecte skill (engine, reuse ladder) and dialecte-contributing when changing this package.
license: MIT
---

# `__DialecteName__` dialecte

`__packageName__` turns the `__DialecteName__` XSD into a typed API over records stored in a database.
The engine (projects, queries, transactions, hooks, import/export) is `@dialecte/core`: read the
`dialecte` skill for it. This page is the map of what THIS package adds, so nobody writes again a
verb or a coherence rule that already exists here.

## Entry points

- `create__DialecteName__Project({ storage, extensions })` from `__packageName__/__version__`.
- `namespace __DialecteName__` for typed refs, records, attributes, query and transaction.
- Tests: `run__DialecteName__TestCases` from `__packageName__/__version__/test`.

## Business verbs (generated from the source)

Search [references/api.md](references/api.md) by what you are trying to do: every verb with its
JSDoc summary and `@intent` tags. The table below is the compact list.

<!-- dialecte-skills:generated extensions -->
<!-- __ifExampleChild__ -->

| Namespace    | On `doc.query.<ns>` | On `tx.<ns>` (writes)    |
| ------------ | ------------------- | ------------------------ |
| `helloWorld` | `sayHello`          | `ensure__ExampleChild__` |

<!-- __endIfExampleChild__ -->
<!-- __ifNoExampleChild__ -->

| Namespace    | On `doc.query.<ns>` | On `tx.<ns>` (writes) |
| ------------ | ------------------- | --------------------- |
| `helloWorld` | `sayHello`          | -                     |

<!-- __endIfNoExampleChild__ -->
<!-- /dialecte-skills:generated -->

When you add a namespace, add one line here saying when to reach for it (`helloWorld` is the
example: delete it with its folder).

## Hooks (generated from the source)

<!-- dialecte-skills:generated hooks -->

This package has no hooks.

<!-- /dialecte-skills:generated -->

For each hook folder, say in one line what it guarantees, so a consumer knows what not to do by
hand.

## Where code goes in this package

| Need                                              | Place                                                                                                                                                                                        |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| a read every consumer of the schema could use     | `src/__version__/extensions/<namespace>/query/<verb>.ts`                                                                                                                                     |
| a write every consumer could use                  | `src/__version__/extensions/<namespace>/transaction/<verb>.ts`                                                                                                                               |
| coherence on every write / import, whoever writes | `src/__version__/hooks/<hook>/<concern>.ts`, wired by `create__DialecteName__Project` passing them as `hooks` to `new Project` (a new package has no hooks folder and passes none: add both) |
| the definition (elements, attributes, types)      | `src/__version__/definition/*.generated.ts` - regenerate, never edit                                                                                                                         |

## Retro gate - before you hand over

List in your hand-over every place where this skill was wrong, missing or misleading for the task,
and every correction the user made that a skill should have prevented. Inside this repository, fix
this page in the same change and run `npm run skills:generate` then `npm run skills:check`. In an
app, draft an issue for this package and post it only with the user's approval. Nothing to report:
write "skill retro: nothing".
