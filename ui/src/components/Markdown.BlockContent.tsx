import React, { FunctionComponent } from "react"

import Registry from "."
import Block from "./Markdown.Block"
import { BlockContent } from "../utils/Markdown"

type OwnProps = {
  content: BlockContent
}

const MarkdownBlockContent: FunctionComponent<OwnProps> = ({ content }) => (
  <>
    {content.map((item, index) => (
      <Block key={index} item={item} />
    ))}
  </>
)

export default Registry.add("Markdown.BlockContent", MarkdownBlockContent)
