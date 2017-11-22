import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."

import { useReview } from "../utils"

const useStyles = makeStyles((theme) => ({
  reviewTitle: {},
  dropped: { textDecoration: "line-through" },
}))

type Props = {
  className?: string
}

const ReviewTitle: FunctionComponent<Props> = () => {
  const classes = useStyles()
  const review = useReview()
  return (
    <Typography
      className={clsx(classes.reviewTitle, {
        [classes.dropped]: review.state === "dropped",
      })}
      variant="h4"
      gutterBottom
    >
      {review.summary}
    </Typography>
  )
}

export default Registry.add("Review.Title", ReviewTitle)
