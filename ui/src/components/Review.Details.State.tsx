import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import DetailsRow from "./Details.Row"
import { useReview } from "../utils/ReviewContext"

const useStyles = makeStyles((theme) => ({
  state: {
    fontWeight: 500,
  },
}))

type OwnProps = {
  className?: string
}

const Labels = {
  draft: "Unpublished",
  dropped: "Dropped",
  closed: "Finished",
}

const ReviewDetailsState: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  const review = useReview()
  if (!review) return null
  // Don't clutter the UI with this information when it's in the boring
  // "default" state.
  if (review.state === "open") return null
  return (
    <DetailsRow className={className} heading="State">
      <span className={classes.state}>{Labels[review.state]}</span>
    </DetailsRow>
  )
}

export default Registry.add("Review.Details.State", ReviewDetailsState)
