import React, { FunctionComponent } from "react"

import Registry from "."
import Heading from "./Markdown.Block.Heading"
import Paragraph from "./Markdown.Block.Paragraph"
import Preformatted from "./Markdown.Block.Preformatted"
import BulletList from "./Markdown.Block.BulletList"
import OrderedList from "./Markdown.Block.OrderedList"
import { BlockContent } from "./Markdown.types"
import Markdown, { BlockContentItem } from "../utils/Markdown"
import { assertNotReached } from "../debug"

type OwnProps = {
  className?: string
  item: BlockContentItem
  BlockContent: BlockContent
}

const MarkdownBlock: FunctionComponent<OwnProps> = ({ item, ...props }) => {
  if (item instanceof Markdown.Heading)
    return <Heading item={item} {...props} />
  if (item instanceof Markdown.Paragraph)
    return <Paragraph item={item} {...props} />
  if (item instanceof Markdown.Preformatted)
    return <Preformatted item={item} {...props} />
  if (item instanceof Markdown.BulletList)
    return <BulletList item={item} {...props} />
  if (item instanceof Markdown.OrderedList)
    return <OrderedList item={item} {...props} />

  assertNotReached()
  return null
}

export default Registry.add("Markdown.Block", MarkdownBlock)
