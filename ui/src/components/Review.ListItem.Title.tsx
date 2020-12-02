import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Review from "../resources/review"

const useStyles = makeStyles({
  reviewListItemTitle: {
    gridArea: "title",
  },
})

type OwnProps = {
  className?: string
  review: Review
}

const ReviewListItemTitle: FunctionComponent<OwnProps> = ({
  className,
  review,
}) => {
  const classes = useStyles()
  return (
    <Typography
      className={clsx(className, classes.reviewListItemTitle)}
      variant="body1"
    >
      {review.summary || (
        <>
          <em>No summary</em>
        </>
      )}
    </Typography>
  )
}

export default Registry.add("Review.ListItem.Title", ReviewListItemTitle)
