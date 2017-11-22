import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import BlockContent from "./Markdown.BlockContent"
import { ListItem } from "../utils/Markdown"

const useStyles = makeStyles((theme) => ({
  markdownBlockListItem: {},
}))

type OwnProps = {
  className?: string
  item: ListItem
}

const MarkdownListItem: FunctionComponent<OwnProps> = ({ className, item }) => {
  const classes = useStyles()
  return (
    <li className={clsx(className, classes.markdownBlockListItem)}>
      <BlockContent content={item.content} />
    </li>
  )
}

export default Registry.add("Markdown.Block.ListItem", MarkdownListItem)
