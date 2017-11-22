import React, { FunctionComponent } from "react"

import Registry from "."
import Heading from "./Markdown.Block.Heading"
import Paragraph from "./Markdown.Block.Paragraph"
import Preformatted from "./Markdown.Block.Preformatted"
import BulletList from "./Markdown.Block.BulletList"
import OrderedList from "./Markdown.Block.OrderedList"
import { BlockContentItem } from "../utils/Markdown"

type OwnProps = {
  className?: string
  item: BlockContentItem
}

const MarkdownBlock: FunctionComponent<OwnProps> = ({ item, ...props }) => {
  switch (item.type) {
    case "heading":
      return <Heading item={item} {...props} />
    case "paragraph":
      return <Paragraph item={item} {...props} />
    case "preformatted":
      return <Preformatted item={item} {...props} />
    case "bullet-list":
      return <BulletList item={item} {...props} />
    case "ordered-list":
      return <OrderedList item={item} {...props} />
  }
}

export default Registry.add("Markdown.Block", MarkdownBlock)
