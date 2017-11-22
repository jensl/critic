import React, { FunctionComponent } from "react"

import Registry from "."
import Inline from "./Markdown.Inline"
import { InlineContent } from "../utils/Markdown"

type OwnProps = {
  content: InlineContent
}

const MarkdownInlineContent: FunctionComponent<OwnProps> = ({ content }) => (
  <>
    {content.map((item, index) => (
      <Inline key={index} item={item} />
    ))}
  </>
)

export default Registry.add("Markdown.InlineContent", MarkdownInlineContent)
