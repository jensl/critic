import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import { useReview } from "../utils"
import Registry from "."

const useStyles = makeStyles((theme) => ({
  reviewSummary: {
    marginTop: theme.spacing(4),
  },
}))

type OwnProps = {
  className?: string
}

const ReviewSummary: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  const review = useReview()
  return (
    <div className={clsx(className, classes.reviewSummary)}>
      <Typography variant="h4">{review.summary}</Typography>
    </div>
  )
}

export default Registry.add("Review.Summary", ReviewSummary)
