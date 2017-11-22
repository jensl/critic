import React, { FunctionComponent } from "react"

import Registry from "."
import InlineContent from "./Markdown.InlineContent"
import { Emphasis } from "../utils/Markdown"

type OwnProps = {
  className?: string
  item: Emphasis
}

const MarkdownEmphasis: FunctionComponent<OwnProps> = ({ className, item }) => {
  const content = <InlineContent content={item.content} />
  if (item.strong) return <strong className={className}>{content}</strong>
  return <em className={className}>{content}</em>
}

export default Registry.add("Markdown.Inline.Emphasis", MarkdownEmphasis)
