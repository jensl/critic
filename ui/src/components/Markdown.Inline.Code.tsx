import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { Code } from "../utils/Markdown"
import { InlineContent } from "./Markdown.types"

const useStyles = makeStyles((theme) => ({
  markdownInlineCode: {
    ...theme.critic.monospaceFont,
    ...theme.critic.standout,
    padding: "1px 6px",
    whiteSpace: "pre",
    color: theme.palette.secondary.contrastText,
  },
}))

type OwnProps = {
  className?: string
  item: Code
  InlineContent: InlineContent
}

const MarkdownCode: FunctionComponent<OwnProps> = ({
  className,
  item,
  InlineContent,
}) => {
  const classes = useStyles()
  return (
    <code className={clsx(className, classes.markdownInlineCode)}>
      <InlineContent content={item.content} />
    </code>
  )
}

export default Registry.add("Markdown.Inline.Code", MarkdownCode)
