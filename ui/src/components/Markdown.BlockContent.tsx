import React, { FunctionComponent } from "react"

import Registry from "."
import Block from "./Markdown.Block"
import { BlockContentProps } from "./Markdown.types"

const BlockContent: FunctionComponent<BlockContentProps> = ({ content }) => (
  <>
    {content.map((item, index) => (
      <Block key={index} item={item} BlockContent={BlockContent} />
    ))}
  </>
)

export default Registry.add("Markdown.BlockContent", BlockContent)
