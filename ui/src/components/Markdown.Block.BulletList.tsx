import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import ListItem from "./Markdown.ListItem"
import { BulletList } from "../utils/Markdown"
import { BlockContent } from "./Markdown.types"

const useStyles = makeStyles((theme) => ({
  markdownBlockBulletList: {},
}))

type OwnProps = {
  className?: string
  item: BulletList
  BlockContent: BlockContent
}

const MarkdownBulletList: FunctionComponent<OwnProps> = ({
  className,
  item,
  BlockContent,
}) => {
  const classes = useStyles()
  return (
    <ul className={clsx(className, classes.markdownBlockBulletList)}>
      {item.items.map((item, index) => (
        <ListItem key={index} item={item} BlockContent={BlockContent} />
      ))}
    </ul>
  )
}

export default Registry.add("Markdown.Block.BulletList", MarkdownBulletList)
