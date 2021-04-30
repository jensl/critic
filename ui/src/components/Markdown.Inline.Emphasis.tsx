import React, { FunctionComponent } from "react"

import Registry from "."
import { Emphasis } from "../utils/Markdown"
import { InlineContent } from "./Markdown.types"

type OwnProps = {
  className?: string
  item: Emphasis
  InlineContent: InlineContent
}

const MarkdownEmphasis: FunctionComponent<OwnProps> = ({
  className,
  item,
  InlineContent,
}) => {
  const content = <InlineContent content={item.content} />
  if (item.strong) return <strong className={className}>{content}</strong>
  return <em className={className}>{content}</em>
}

export default Registry.add("Markdown.Inline.Emphasis", MarkdownEmphasis)
