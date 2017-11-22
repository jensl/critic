import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import InlineContent from "./Markdown.InlineContent"
import { Paragraph } from "../utils/Markdown"

const useStyles = makeStyles((theme) => ({
  markdownBlockParagraph: {
    textAlign: "justify",
  },
}))

type OwnProps = {
  className?: string
  item: Paragraph
}

const MarkdownParagraph: FunctionComponent<OwnProps> = ({
  className,
  item,
}) => {
  const classes = useStyles()
  return (
    <Typography
      variant="body1"
      className={clsx(className, classes.markdownBlockParagraph)}
      gutterBottom
    >
      <InlineContent content={item.content} />
    </Typography>
  )
}

export default Registry.add("Markdown.Block.Paragraph", MarkdownParagraph)
