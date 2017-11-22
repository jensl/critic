import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import BlockContent from "./Markdown.BlockContent"
import Markdown from "../utils/Markdown"

const useStyles = makeStyles((theme) => ({
  markdownDocument: {
    margin: theme.spacing(1, 0),
  },
}))

type OwnProps = {
  className?: string
  source?: string
}

const MarkdownDocument: FunctionComponent<OwnProps> = ({
  className,
  source,
  children,
}) => {
  const classes = useStyles()

  if (typeof source !== "string") {
    source = ""
    React.Children.map(children, (child: any) => {
      if (typeof child === "string") source += child
    })
  }

  const document = Markdown.parse(source)

  return (
    <div className={clsx(className, classes.markdownDocument)}>
      <BlockContent content={document.content} />
    </div>
  )
}

export default Registry.add("Markdown.Document", MarkdownDocument)
