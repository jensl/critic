import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import ListItem from "./Markdown.ListItem"
import { OrderedList } from "../utils/Markdown"

const useStyles = makeStyles((theme) => ({
  markdownBlockOrderedList: {},
}))

type OwnProps = {
  className?: string
  item: OrderedList
}

const MarkdownOrderedList: FunctionComponent<OwnProps> = ({
  className,
  item,
}) => {
  const classes = useStyles()
  return (
    <ul className={clsx(className, classes.markdownBlockOrderedList)}>
      {item.items.map((item, index) => (
        <ListItem key={index} item={item} />
      ))}
    </ul>
  )
}

export default Registry.add("Markdown.Block.OrderedList", MarkdownOrderedList)
