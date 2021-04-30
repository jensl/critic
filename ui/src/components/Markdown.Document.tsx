import React from "react"
import loadable from "@loadable/component"

import Registry from "."

type Props = {
  className?: string
  source?: string
  summary?: boolean
}

const MarkdownDocument = loadable(
  () => import("./Markdown.Document.lazy"),
) as React.FunctionComponent<Props>

export default Registry.add("Markdown.Document", MarkdownDocument)
