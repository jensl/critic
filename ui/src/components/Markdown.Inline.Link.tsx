import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import MUILink from "@material-ui/core/Link"

import Registry from "."
import InlineContent from "./Markdown.InlineContent"
import { Link } from "../utils/Markdown"

const useStyles = makeStyles((theme) => ({
  markdownInlineLink: {},
}))

type OwnProps = {
  className?: string
  item: Link
}

const MarkdownLink: FunctionComponent<OwnProps> = ({ className, item }) => {
  const classes = useStyles()
  return (
    <MUILink
      className={clsx(className, classes.markdownInlineLink)}
      href={item.href}
    >
      <InlineContent content={item.content} />
    </MUILink>
  )
}

export default Registry.add("Markdown.Inline.Link", MarkdownLink)
