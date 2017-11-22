import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import InlineContent from "./Markdown.InlineContent"
import { Heading } from "../utils/Markdown"

const useStyles = makeStyles((theme) => ({
  markdownBlockHeading: {
    marginTop: "1rem",
  },

  h1: {
    fontSize: "3rem",
  },
  h2: {
    fontSize: "200%",
    marginTop: "2rem",
  },
  h3: {
    fontSize: "150%",
  },
  h4: {
    fontSize: "120%",
  },
  h5: {
    fontSize: "120%",
  },
  h6: {
    fontSize: "120%",
  },
}))

type OwnProps = {
  className?: string
  item: Heading
}

const MarkdownHeading: FunctionComponent<OwnProps> = ({ className, item }) => {
  const classes = useStyles()
  return (
    <Typography
      variant={item.tag}
      className={clsx(
        className,
        classes.markdownBlockHeading,
        classes[item.tag]
      )}
      gutterBottom
    >
      <InlineContent content={item.content} />
    </Typography>
  )
}

export default Registry.add("Markdown.Block.Heading", MarkdownHeading)
