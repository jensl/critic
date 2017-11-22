import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Commit from "../resources/commit"

const useStyles = makeStyles((theme) => ({
  commitListItemSHA1: {
    gridArea: "sha1",
    textAlign: "right",
    ...theme.critic.monospaceFont,
  },
}))

type Props = {
  className?: string
  commit: Commit
}

const CommitListItemSHA1: FunctionComponent<Props> = ({
  className,
  commit,
}) => {
  const classes = useStyles()
  return (
    <Typography
      className={clsx(className, classes.commitListItemSHA1)}
      variant="body1"
    >
      {commit.sha1.substring(0, 8)}
    </Typography>
  )
}

export default Registry.add("Commit.ListItem.SHA1", CommitListItemSHA1)
