import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import CommitList from "./Commit.List"
import Rebase from "./Review.Commits.Rebase"
import { useReview } from "../utils"
import { Partition } from "../resources/review"

const useStyles = makeStyles((theme) => ({
  reviewCommitsPartition: {},
}))

type Props = {
  className?: string
  index: number
  partition: Partition
}

const ReviewCommitsPartition: FunctionComponent<Props> = ({
  className,
  index,
  partition,
}) => {
  const classes = useStyles()
  const review = useReview()
  if (!review) return null
  const rebase =
    partition.rebase !== null ? <Rebase rebaseID={partition.rebase} /> : null
  return (
    <>
      <CommitList
        className={clsx(className, classes.reviewCommitsPartition)}
        pathPrefix={`/review/${review.id}`}
        scopeID={`partition${index}`}
        commitIDs={partition.commits}
        withProgress
      />
      {rebase}
    </>
  )
}

export default Registry.add("Review.Commits.Partition", ReviewCommitsPartition)
