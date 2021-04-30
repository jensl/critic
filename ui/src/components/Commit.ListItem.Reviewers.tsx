import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import UserChips from "./User.Chips"
import Commit from "../resources/commit"
import { useSelector } from "../store"
import { getReviewableFileChangesPerReviewAndCommit } from "../selectors/reviewableFileChange"
import { useOptionalReview } from "../utils"
import { map, mergedSets } from "../utils/Functions"

const useStyles = makeStyles({
  commitListItemReviewers: {
    gridArea: "reviewers",
    opacity: 0.5,
  },
})

type Props = {
  className?: string
  commit: Commit
}

const Reviewers: FunctionComponent<Props> = ({ className, commit }) => {
  const classes = useStyles()
  const review = useOptionalReview()
  const rfcsPerReview = useSelector(getReviewableFileChangesPerReviewAndCommit)
  const rfcs = rfcsPerReview.get(review?.id ?? -1)?.get(commit.id)
  if (!rfcs) return null
  const userIDs = mergedSets(...map(rfcs, (rfc) => rfc.reviewedBy))
  if (userIDs.size === 0) return null
  return (
    <Typography
      className={clsx(className, classes.commitListItemReviewers)}
      component="div"
      variant="body2"
    >
      reviewed by{" "}
      <UserChips
        UserChipProps={{ ChipProps: { size: "small" } }}
        userIDs={userIDs}
      />
    </Typography>
  )
}

export default Registry.add("Commit.ListItem.Reviewers", Reviewers)
