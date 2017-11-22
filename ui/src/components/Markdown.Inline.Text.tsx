import React, { FunctionComponent } from "react"

import Registry from "."
import { Text } from "../utils/Markdown"

type OwnProps = {
  item: Text
}

const MarkdownText: FunctionComponent<OwnProps> = ({ item }) => (
  <>{item.value}</>
)

export default Registry.add("Markdown.Inline.Text", MarkdownText)
