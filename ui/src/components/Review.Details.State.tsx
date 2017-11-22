import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import DetailsRow from "./Details.Row"
import { useReview } from "../utils/ReviewContext"

const useStyles = makeStyles({
  root: {},

  dropped: {
    color: "red",
    fontWeight: 500,
  },
})

type OwnProps = {
  className?: string
}

const ReviewDetailsState: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  const review = useReview()
  if (!review) return null
  // Don't clutter the UI with this information when it's in the boring
  // "default" state.
  if (review.state === "open") return null
  const states = {
    draft: <span className={classes.dropped}>Unpublished</span>,
    dropped: <span className={classes.dropped}>Dropped</span>,
    closed: <span className={classes.dropped}>Finished</span>,
  }
  return <DetailsRow heading="State">{states[review.state]}</DetailsRow>
}

export default Registry.add("Review.Details.State", ReviewDetailsState)
