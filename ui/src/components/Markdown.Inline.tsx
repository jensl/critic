import React, { FunctionComponent } from "react"

import Registry from "."
import Text from "./Markdown.Inline.Text"
import Link from "./Markdown.Inline.Link"
import Code from "./Markdown.Inline.Code"
import Emphasis from "./Markdown.Inline.Emphasis"
import { InlineContentItem } from "../utils/Markdown"

type OwnProps = {
  className?: string
  item: InlineContentItem
}

const MarkdownInline: FunctionComponent<OwnProps> = ({ item, ...props }) => {
  switch (item.type) {
    case "text":
      return <Text item={item} {...props} />
    case "link":
      return <Link item={item} {...props} />
    case "code":
      return <Code item={item} {...props} />
    case "emphasis":
      return <Emphasis item={item} {...props} />
  }
}

export default Registry.add("Markdown.Inline", MarkdownInline)
