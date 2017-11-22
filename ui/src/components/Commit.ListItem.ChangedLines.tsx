import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import { getReviewableFileChangesPerReviewAndCommit } from "../selectors/reviewableFileChange"
import { useReview } from "../utils"
import Commit from "../resources/commit"
import { useSelector } from "../store"

const useStyles = makeStyles((theme) => ({
  root: {
    gridArea: "lines",
    textAlign: "right",
    ...theme.critic.monospaceFont,
  },
}))

type Props = {
  className?: string
  commit: Commit
}

const CommitListItemChangedLines: FunctionComponent<Props> = ({
  className,
  commit,
}) => {
  const classes = useStyles()
  const review = useReview()
  const rfcsPerReview = useSelector(getReviewableFileChangesPerReviewAndCommit)
  if (!review) return null
  const rfcsPerCommit = rfcsPerReview.get(review.id)
  if (!rfcsPerCommit) return null
  const rfcs = rfcsPerCommit.get(commit.id)
  if (!rfcs) return null
  var deletedLines = 0
  var insertedLines = 0
  for (const rfc of rfcs) {
    deletedLines += rfc.deletedLines
    insertedLines += rfc.insertedLines
  }
  return (
    <Typography className={clsx(className, classes.root)} variant="body1">
      -{deletedLines}/+{insertedLines}
    </Typography>
  )
}

export default Registry.add(
  "Commit.ListItem.ChangedLines",
  CommitListItemChangedLines
)
