import React, { FunctionComponent } from "react"

import Registry from "."
import Text from "./Markdown.Inline.Text"
import Link from "./Markdown.Inline.Link"
import Code from "./Markdown.Inline.Code"
import Emphasis from "./Markdown.Inline.Emphasis"
import Markdown, { InlineContentItem } from "../utils/Markdown"
import { InlineContent } from "./Markdown.types"
import { assertNotReached } from "../debug"

type OwnProps = {
  className?: string
  item: InlineContentItem
  InlineContent: InlineContent
}

const MarkdownInline: FunctionComponent<OwnProps> = ({ item, ...props }) => {
  if (item instanceof Markdown.Inline.Text)
    return <Text item={item} {...props} />
  if (item instanceof Markdown.Inline.Link)
    return <Link item={item} {...props} />
  if (item instanceof Markdown.Inline.Code)
    return <Code item={item} {...props} />
  if (item instanceof Markdown.Inline.Emphasis)
    return <Emphasis item={item} {...props} />

  assertNotReached()
  return null
}

export default Registry.add("Markdown.Inline", MarkdownInline)
