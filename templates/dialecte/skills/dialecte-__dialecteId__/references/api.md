# `__packageName__` API index

Generated from the source by `npm run skills:generate`: every verb this package adds to `doc.query`
and `tx`, with the first paragraph of its JSDoc and its `@intent` tags. Look up your need in the
first table, then read the verb's row; read a close verb's JSDoc and tests before ruling it out.

## When you need to...

<!-- dialecte-skills:generated intents -->
<!-- __ifExampleChild__ -->

| When you need to... | Use |
|---|---|
| add a __exampleChild__ once (get or create) | `tx.helloWorld.ensure__ExampleChild__` |
| count what a document is made of | `doc.query.helloWorld.sayHello` |
| example of a read extension | `doc.query.helloWorld.sayHello` |
| example of a write extension | `tx.helloWorld.ensure__ExampleChild__` |

<!-- __endIfExampleChild__ -->
<!-- __ifNoExampleChild__ -->

| When you need to... | Use |
|---|---|
| count what a document is made of | `doc.query.helloWorld.sayHello` |
| example of a read extension | `doc.query.helloWorld.sayHello` |

<!-- __endIfNoExampleChild__ -->
<!-- /dialecte-skills:generated -->

## Methods

<!-- dialecte-skills:generated api -->
<!-- __ifExampleChild__ -->

| Method | What it answers | Reach for it to |
|---|---|---|
| `doc.query.helloWorld.sayHello` | The smallest useful read: what is this document made of? | count what a document is made of; example of a read extension |
| `tx.helloWorld.ensure__ExampleChild__` | The smallest useful write: make sure the __exampleRoot__ holds a __exampleChild__. `ensureChild` is get-or-create: a __exampleChild__ already there with these attributes is handed back as it is, so running this twice never adds a second one. | add a __exampleChild__ once (get or create); example of a write extension |

<!-- __endIfExampleChild__ -->
<!-- __ifNoExampleChild__ -->

| Method | What it answers | Reach for it to |
|---|---|---|
| `doc.query.helloWorld.sayHello` | The smallest useful read: what is this document made of? | count what a document is made of; example of a read extension |

<!-- __endIfNoExampleChild__ -->
<!-- /dialecte-skills:generated -->
