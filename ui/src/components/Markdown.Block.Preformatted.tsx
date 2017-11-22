import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { Preformatted } from "../utils/Markdown"

const useStyles = makeStyles((theme) => ({
  markdownBlockPreformatted: {
    ...theme.critic.monospaceFont,
    ...theme.critic.standout,
    fontWeight: 500,
    padding: `${theme.spacing(1)}px ${theme.spacing(2)}px`,
    marginLeft: theme.spacing(3),
    marginRight: theme.spacing(3),
  },
}))

type OwnProps = {
  className?: string
  item: Preformatted
}

const MarkdownPreformatted: FunctionComponent<OwnProps> = ({
  className,
  item,
}) => {
  const classes = useStyles()
  return (
    <pre className={clsx(className, classes.markdownBlockPreformatted)}>
      {item.value}
    </pre>
  )
}

export default Registry.add("Markdown.Block.Preformatted", MarkdownPreformatted)
