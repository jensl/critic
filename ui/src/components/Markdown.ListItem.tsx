import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { BlockContent } from "./Markdown.types"
import { ListItem } from "../utils/Markdown"

const useStyles = makeStyles((theme) => ({
  markdownBlockListItem: {},
}))

type OwnProps = {
  className?: string
  item: ListItem
  BlockContent: BlockContent
}

const MarkdownListItem: FunctionComponent<OwnProps> = ({
  className,
  item,
  BlockContent,
}) => {
  const classes = useStyles()
  return (
    <li className={clsx(className, classes.markdownBlockListItem)}>
      <BlockContent content={item.content} />
    </li>
  )
}

export default Registry.add("Markdown.Block.ListItem", MarkdownListItem)
