/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import MarkdownIt from "markdown-it"

import {
  assertEqual,
  assertNotEqual,
  assertNotReached,
  assertString,
} from "../debug"

const parse = (source: string) => process(new MarkdownIt().parse(source, {}))

interface TokenType<Token> {
  type: string
  tag: string
  attrs: [string, string][] | null
  info: string
  children: Token[] | null
  content: string
  markup: string
}

const process = <Token extends TokenType<Token>>(tokens: Token[]) => {
  const findAttribute = (
    attributes: [string, string][] | null,
    name: string,
  ): string | undefined => {
    if (attributes)
      for (const [attributeName, attributeValue] of attributes)
        if (attributeName === name) return attributeValue
  }

  const containedTokens = (tokens: Token[], index: number) => {
    const openType = tokens[index].type
    const closeType = openType.replace("_open", "_close")
    assertNotEqual(openType, closeType)
    const result = []
    var nesting = 1
    while (nesting > 0) {
      const token = tokens[++index]
      switch (token.type) {
        case closeType:
          --nesting
          break
        case openType:
          ++nesting
          break
        default:
          break
      }
      if (nesting > 0) result.push(token)
    }
    return result
  }

  const makeInline = (token: {
    children: Token[] | null
    content?: string
  }): InlineContent => {
    if (!token.children) {
      assertString(token.content)
      return makeInlineContent([new Markdown.Inline.Text(token.content)])
    }
    const children: (string | InlineContentItem)[] = []
    const addText = (value: string) => {
      if (
        children.length &&
        typeof children[children.length - 1] === "string"
      ) {
        children[children.length - 1] += value
      } else {
        children.push(value)
      }
    }
    const addChild = (item: InlineContentItem) => children.push(item)
    for (let index = 0; index < token.children.length; ++index) {
      const item: Token = token.children[index]
      switch (item.type) {
        case "text":
          addText(item.content)
          break
        case "softbreak":
          addText(" ")
          break
        case "link_open": {
          const linkTokens = containedTokens(token.children, index)
          index += linkTokens.length + 1
          addChild(
            new Markdown.Inline.Link(
              makeInline({ children: linkTokens }),
              findAttribute(item.attrs, "href") ?? "#",
            ),
          )
          break
        }
        case "code_inline":
          addChild(new Markdown.Inline.Code(makeInline(item)))
          break
        case "inline":
          for (const child of makeInline(item)) children.push(child)
          break
        case "em_open":
        case "strong_open":
          const emTokens = containedTokens(token.children, index)
          index += emTokens.length + 1
          addChild(
            new Markdown.Inline.Emphasis(
              makeInline({ children: emTokens }),
              item.type === "strong_open",
            ),
          )
          break
        default:
          console.error({ item })
          assertNotReached()
      }
    }
    const postProcess = (children: (string | InlineContentItem)[]) =>
      children.map((child) => {
        if (typeof child !== "string") return child
        return new Markdown.Inline.Text(child)
      })
    return makeInlineContent(postProcess(children))
  }

  function* processListTokens(tokens: Token[]) {
    for (let index = 0; index < tokens.length; ++index) {
      const item = tokens[index]
      switch (item.type) {
        case "list_item_open": {
          const itemTokens = containedTokens(tokens, index)
          index += itemTokens.length + 1
          yield new Markdown.ListItem(
            makeBlockContent(processBlockTokens(itemTokens)),
          )
          break
        }
        default:
          assertNotReached()
      }
    }
  }

  function* processBlockTokens(tokens: Token[]): Iterable<BlockContentItem> {
    for (let index = 0; index < tokens.length; ++index) {
      const token = tokens[index]
      switch (token.type) {
        case "heading_open": {
          const headingTokens = containedTokens(tokens, index)
          index += headingTokens.length + 1
          yield new Markdown.Heading(
            token.tag as HeadingTag,
            makeInline({ children: headingTokens }),
          )
          break
        }
        case "paragraph_open": {
          const paragraphTokens = containedTokens(tokens, index)
          index += paragraphTokens.length + 1
          yield new Markdown.Paragraph(
            makeInline({ children: paragraphTokens }),
          )
          break
        }
        case "bullet_list_open": {
          const listTokens = containedTokens(tokens, index)
          index += listTokens.length + 1
          yield new Markdown.BulletList([...processListTokens(listTokens)])
          break
        }
        case "ordered_list_open": {
          const listTokens = containedTokens(tokens, index)
          index += listTokens.length + 1
          yield new Markdown.OrderedList([...processListTokens(listTokens)])
          break
        }
        case "code_block": {
          yield new Markdown.Preformatted(null, token.content)
          break
        }
        case "fence": {
          yield new Markdown.Preformatted(token.info, token.content)
          break
        }
        default:
          console.error({ token })
          assertNotReached()
      }
    }
  }

  const inlineAsString = (content: InlineContent): string =>
    content
      .map((item) =>
        (item instanceof Text
          ? item.value
          : inlineAsString(item.content)
        ).trim(),
      )
      .join(" ")

  const content = [...processBlockTokens(tokens)]
  const firstItem = content[0]
  const title =
    firstItem instanceof Heading ? inlineAsString(firstItem.content) : null

  return new Markdown.Document(title, content, new Map())
}

export type InlineContentItem = Text | Link | Code | Emphasis
export type InlineContent = InlineContentItem[]
const makeInlineContent = (items: Iterable<InlineContentItem> = []) => [
  ...items,
]

export type BlockContentItem =
  | Heading
  | Paragraph
  | Preformatted
  | BulletList
  | OrderedList
export type BlockContent = BlockContentItem[]
const makeBlockContent = (items: Iterable<BlockContentItem> = []) => [...items]

export class Document {
  constructor(
    readonly title: string | null,
    readonly content: BlockContent,
    readonly links: ReadonlyMap<string, Link>,
  ) {}
}

type HeadingTag = "h1" | "h2" | "h3" | "h4" | "h5" | "h6"
export class Heading {
  static type = "heading"

  constructor(readonly tag: HeadingTag, readonly content: InlineContent) {}
}

export class Paragraph {
  static type = "paragraph"

  constructor(readonly content: InlineContent) {}
}

export class Preformatted {
  static type = "preformatted"

  constructor(readonly language: string | null, readonly value: string) {}
}

export class BulletList {
  static type = "bullet-list"

  constructor(readonly items: readonly ListItem[]) {}
}

export class OrderedList {
  static type = "ordered-list"

  constructor(readonly items: readonly ListItem[]) {}
}

export class ListItem {
  static type = "list-item"

  constructor(readonly content: BlockContent) {}
}

export class Text {
  static type = "text"

  constructor(readonly value: string) {}
}

export class Link {
  static type = "link"

  constructor(readonly content: InlineContent, readonly href: string) {}
}

export class Code {
  static type = "code"

  constructor(readonly content: InlineContent) {}
}

export class Emphasis {
  static type = "emphasis"

  constructor(readonly content: InlineContent, readonly strong: boolean) {}
}

const Inline = {
  Text,
  Link,
  Code,
  Emphasis,
}

const Markdown = {
  Document,
  Heading,
  Paragraph,
  Preformatted,
  BulletList,
  OrderedList,
  ListItem,
  Inline,
  parse,
}

export default Markdown
