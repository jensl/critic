# UI style guide

## Formatting

[Prettier](https://prettier.io/) is used for formatting of all source code. Its
behavior, given our configuration of it, is law. Most of the following is thus
just consequence of that. When editing code, most of these rules can be ignored
since Prettier will fix almost everything.

- Lines should be no longer than 80 characters. The exception is imports that
  import a single item, which Prettier intentionally formats on a single line,
  regardless of the length.

- No semicolons at the end of statements.

- Include trailing commas in contexts (like array and object literals) where
  this is supported in ECMAScript 5.

- Define functions using the arrow function syntax, except in the following
  cases:

- Member functions in classes, which use the `name() { ... }` short-form.

- Generators, which use the `function* () { ... }` syntax (no arrow function
  syntax is available for generators.)

### Small compound statements

Small compound statements, like `if`-statements with trivial controlled
statements, come in two forms:

```
// Used when it all fits on one line.
if (condition) statement
```

```
// Used when it all doesn't fit on one line, or when otherwise appropriate.
if (condition) {
    statement
}
```

Note that Prettier allows both, i.e. it formats according to whether a `{`/`}`
pair was inserted, rather than inserting them. It can produce a third form that
we don't want: a two-line form without `{`/`}` if the first form doesn't fit on
a single line. In this case, insert `{`/`}` to have Prettier format to the
second form.

### JSX

Multi-line JSX is always wrapped in parentheses, like this:

```
return (
    <div>
        Hello world!
    </div>
)
```

Multi-line JSX tags are formatted with the trailing `>` on its own line, like
this:

```
<SomeComponent
    someAttribute={someVariable}
    someOtherAttribute={someOtherVariable}
>
    <div>Some content</div>
</SomeComponent>
```

## Imports

Imports are divided into three blocks, separated by a blank line:

- External imports, from packages such as `"react"` and `"redux"`.

- Internal imports, from directories such as `ui/src/components/` and
  `ui/src/containers/`.

- Non-JS imports, such as CSS files.

Naturally, any of the three blocks may be omitted.

## React components

When possible, implement presentational components as stateless functions rather
than as classes. Since Redux is used, components should not manage any state
directly anyway, so a function is almost always sufficient.

```
// Presentational component implemented as stateless function
const SomeComponent = props => {
    ...
    return (
        <div className="some_component">
            ...
        </div>
    )
}
```

The exception is components that should trigger side-effects when mounted, or
when their `props` change. However, when possible, we prefer to use higher order
components for these purposes, to avoid mixing presentation and logic.

Examples of such higher order components are `withSubscriptions()` in
`ui/src/utils/ResourceSubscriber.js` that loads resources when mounted, and
`withKeyboardShortcuts()` in `ui/src/utils/KeyboardShortcuts.js` that registers
keyboard shortcuts while mounted.
