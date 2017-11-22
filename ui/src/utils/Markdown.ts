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
import Immutable, { Record, List, Map } from "immutable"

import { assertEqual, assertNotEqual, assertNotReached } from "../debug"

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
    name: string
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
      assertEqual(typeof token.content, "string")
      return makeInlineContent([
        new Markdown.Inline.Text({ value: token.content }),
      ])
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
            new Markdown.Inline.Link({
              href: findAttribute(item.attrs, "href"),
              content: makeInline({ children: linkTokens }),
            })
          )
          break
        }
        case "code_inline":
          addChild(
            new Markdown.Inline.Code({
              content: makeInline(item),
            })
          )
          break
        case "inline":
          for (const child of makeInline(item)) children.push(child)
          break
        case "em_open":
        case "strong_open":
          const emTokens = containedTokens(token.children, index)
          index += emTokens.length + 1
          addChild(
            new Markdown.Inline.Emphasis({
              content: makeInline({ children: emTokens }),
              strong: item.type === "strong_open",
            })
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
        return new Markdown.Inline.Text({ value: child })
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
          yield new Markdown.ListItem({
            content: makeBlockContent(processBlockTokens(itemTokens)),
          })
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
          yield new Markdown.Heading({
            tag: token.tag as HeadingTag,
            content: makeInline({ children: headingTokens }),
          })
          break
        }
        case "paragraph_open": {
          const paragraphTokens = containedTokens(tokens, index)
          index += paragraphTokens.length + 1
          yield new Markdown.Paragraph({
            content: makeInline({ children: paragraphTokens }),
          })
          break
        }
        case "bullet_list_open": {
          const listTokens = containedTokens(tokens, index)
          index += listTokens.length + 1
          yield new Markdown.BulletList({
            items: Immutable.List(processListTokens(listTokens)),
          })
          break
        }
        case "ordered_list_open": {
          const listTokens = containedTokens(tokens, index)
          index += listTokens.length + 1
          yield new Markdown.OrderedList({
            items: Immutable.List(processListTokens(listTokens)),
          })
          break
        }
        case "code_block": {
          yield new Markdown.Preformatted({
            value: token.content,
          })
          break
        }
        case "fence": {
          yield new Markdown.Preformatted({
            language: token.info,
            value: token.content,
          })
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
        (item.type === "text"
          ? item.value
          : inlineAsString(item.content)
        ).trim()
      )
      .join(" ")

  const content = Immutable.List<BlockContentItem>(processBlockTokens(tokens))
  const firstItem = content.first<BlockContentItem | null>()
  const title =
    firstItem && firstItem.type === "heading"
      ? inlineAsString(firstItem.content)
      : null

  return new Markdown.Document({
    title,
    content,
  })
}

export type InlineContentItem = Text | Link | Code | Emphasis
export type InlineContent = Immutable.List<InlineContentItem>
const makeInlineContent = (items: Iterable<InlineContentItem> = []) =>
  Immutable.List<InlineContentItem>(items)

export type BlockContentItem =
  | Heading
  | Paragraph
  | Preformatted
  | BulletList
  | OrderedList
export type BlockContent = Immutable.List<BlockContentItem>
const makeBlockContent = (items: Iterable<BlockContentItem> = []) =>
  Immutable.List<BlockContentItem>(items)

type DocumentProps = {
  title: string | null
  content: BlockContent
  links: Immutable.Map<string, Link>
}

export class Document extends Record<DocumentProps>(
  {
    title: null,
    content: makeBlockContent(),
    links: Immutable.Map<string, Link>(),
  },
  "Markdown.Document"
) {}

type HeadingTag = "h1" | "h2" | "h3" | "h4" | "h5" | "h6"
type HeadingProps = {
  type: "heading"
  tag: HeadingTag
  content: InlineContent
}
export class Heading extends Immutable.Record<HeadingProps>(
  {
    type: "heading",
    tag: "h1",
    content: makeInlineContent(),
  },
  "Markdown.Heading"
) {}

type ParagraphProps = {
  type: "paragraph"
  content: InlineContent
}
export class Paragraph extends Immutable.Record<ParagraphProps>(
  {
    type: "paragraph",
    content: makeInlineContent(),
  },
  "Markdown.Paragraph"
) {}

type PreformattedProps = {
  type: "preformatted"
  language: string
  value: string
}
export class Preformatted extends Immutable.Record<PreformattedProps>(
  {
    type: "preformatted",
    language: "",
    value: "",
  },
  "Markdown.Preformatted"
) {}

type BulletListProps = {
  type: "bullet-list"
  items: Immutable.List<ListItem>
}
export class BulletList extends Immutable.Record<BulletListProps>(
  {
    type: "bullet-list",
    items: Immutable.List<ListItem>(),
  },
  "Markdown.BulletList"
) {}

type OrderedListProps = {
  type: "ordered-list"
  items: Immutable.List<ListItem>
}
export class OrderedList extends Immutable.Record<OrderedListProps>(
  {
    type: "ordered-list",
    items: Immutable.List<ListItem>(),
  },
  "Markdown.OrderedList"
) {}

type ListItemProps = {
  type: "list-item"
  content: BlockContent
}
export class ListItem extends Immutable.Record<ListItemProps>(
  {
    type: "list-item",
    content: makeBlockContent(),
  },
  "Markdown.ListItem"
) {}

/* type InlineProps = {
children: Immutable.Link
}
export class Inline extends Immutable.Record<>(
  {
    children: Immutable.List(),
  },
  "Markdown.Inline"
)
 */

type TextProps = {
  type: "text"
  value: string
}
export class Text extends Immutable.Record<TextProps>(
  {
    type: "text",
    value: "",
  },
  "Markdown.Inline.Text"
) {}

type LinkProps = {
  type: "link"
  content: InlineContent
  href: string
}
export class Link extends Immutable.Record<LinkProps>(
  {
    type: "link",
    content: makeInlineContent(),
    href: "",
  },
  "Markdown.Inline.Link"
) {}

type CodeProps = {
  type: "code"
  content: InlineContent
}
export class Code extends Immutable.Record<CodeProps>(
  {
    type: "code",
    content: makeInlineContent(),
  },
  "Markdown.Inline.Code"
) {}

type EmphasisProps = {
  type: "emphasis"
  content: InlineContent
  strong: boolean
}
export class Emphasis extends Immutable.Record<EmphasisProps>(
  {
    type: "emphasis",
    content: makeInlineContent(),
    strong: false,
  },
  "Markdown.Inline.Emphasis"
) {}

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
