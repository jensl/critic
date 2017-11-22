import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import LinearProgress from "@material-ui/core/LinearProgress"

import Registry from "."
import { useReview } from "../utils/ReviewContext"

const useStyles = makeStyles((theme) => ({
  reviewProgress: { marginBottom: theme.spacing(3) },
}))

type OwnProps = {
  className?: string
}

const ReviewProgress: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  const review = useReview()
  return (
    <LinearProgress
      className={clsx(className, classes.reviewProgress)}
      color="primary"
      value={review.progress.reviewing * 100}
      variant="determinate"
    />
  )
}

export default Registry.add("Review.Progress", ReviewProgress)
