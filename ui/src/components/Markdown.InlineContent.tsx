import React, { FunctionComponent } from "react"

import Registry from "."
import Inline from "./Markdown.Inline"
import { InlineContentProps } from "./Markdown.types"

const InlineContent: FunctionComponent<InlineContentProps> = ({ content }) => (
  <>
    {content.map((item, index) => (
      <Inline key={index} item={item} InlineContent={InlineContent} />
    ))}
  </>
)

export default Registry.add("Markdown.InlineContent", InlineContent)
