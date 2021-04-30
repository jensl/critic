import React from "react"

import {
  BlockContent as MDBlockContent,
  InlineContent as MDInlineContent,
} from "../utils/Markdown"

export type BlockContentProps = {
  content: MDBlockContent
}

export type BlockContent = React.FunctionComponent<BlockContentProps>

export type InlineContentProps = {
  content: MDInlineContent
}

export type InlineContent = React.FunctionComponent<InlineContentProps>
