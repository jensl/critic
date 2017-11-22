import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import timeSince from "../utils/TimeSince"
import Commit from "../resources/commit"

const useStyles = makeStyles({
  commitListItemMetadata: {
    gridArea: "metadata",
    opacity: 0.5,
  },
})

type Props = {
  className?: string
  commit: Commit
}

const CommitListItemMetadata: FunctionComponent<Props> = ({
  className,
  commit,
}) => {
  const classes = useStyles()
  return (
    <Typography
      className={clsx(className, classes.commitListItemMetadata)}
      variant="body2"
    >
      by {commit.author.name} ({timeSince(commit.author.timestamp)} ago)
    </Typography>
  )
}

export default Registry.add("Commit.ListItem.Metadata", CommitListItemMetadata)
