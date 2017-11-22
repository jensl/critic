import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"
import CircularProgress from "@material-ui/core/CircularProgress"
import CheckIcon from "@material-ui/icons/Check"

import Registry from "."
import { useReview } from "../utils"
import Commit from "../resources/commit"

const useStyles = makeStyles((theme) => ({
  commitListItemProgress: {
    gridArea: "progress",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    paddingRight: "1rem",
  },
  done: {
    color: theme.palette.success.main,
  },
  background: {
    color: "#ccc",
    position: "absolute",
  },
  value: {
    position: "absolute",
  },
}))

type Props = {
  className?: string
  commit: Commit
}

const CommitListItemProgress: FunctionComponent<Props> = ({
  className,
  commit,
}) => {
  const classes = useStyles()
  const review = useReview()
  if (!review || !review.progressPerCommit) return null
  const progress = review.progressPerCommit.get(commit.id)
  if (!progress) return null
  var content
  if (progress.totalChanges === progress.reviewedChanges)
    content = <CheckIcon className={classes.done} fontSize="large" />
  else if (progress.reviewedChanges === 0) return null
  else
    content = (
      <>
        <CircularProgress
          className={classes.background}
          variant="static"
          value={100}
        />
        <CircularProgress
          className={classes.value}
          variant="static"
          value={(progress.reviewedChanges / progress.totalChanges) * 100}
        />
      </>
    )
  return <div className={classes.commitListItemProgress}>{content}</div>
}

export default Registry.add("Commit.ListItem.Progress", CommitListItemProgress)
