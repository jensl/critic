import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Commit from "../resources/commit"

const useStyles = makeStyles((theme) => ({
  commitListItemSummary: {
    gridArea: "summary",
    ...theme.critic.monospaceFont,
    //fontWeight: 500,
    //fontSize: "110%",
  },
}))

type Props = {
  className?: string
  commit: Commit
}

const CommitListItemSummary: FunctionComponent<Props> = ({
  className,
  commit,
}) => {
  const classes = useStyles()
  return (
    <Typography
      className={clsx(className, classes.commitListItemSummary)}
      variant="body1"
    >
      {commit.summary}
    </Typography>
  )
}

export default Registry.add("Commit.ListItem.Summary", CommitListItemSummary)
