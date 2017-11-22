import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import CircularProgress from "@material-ui/core/CircularProgress"
import CheckIcon from "@material-ui/icons/Check"

import Registry from "."
import Review from "../resources/review"

const useStyles = makeStyles((theme) => ({
  reviewListItemProgress: {
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

type OwnProps = {
  className?: string
  review: Review
}

const ReviewListItemProgress: FunctionComponent<OwnProps> = ({
  className,
  review,
}) => {
  const classes = useStyles()
  var content
  if (review.state === "closed" || review.isAccepted)
    content = <CheckIcon className={classes.done} fontSize="large" />
  else if (review.progress.reviewing === 0) content = null
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
          value={review.progress.reviewing * 100}
          thickness={4}
        />
      </>
    )

  return (
    <div className={clsx(className, classes.reviewListItemProgress)}>
      {content}
    </div>
  )
}

export default Registry.add("Review.ListItem.Progress", ReviewListItemProgress)
