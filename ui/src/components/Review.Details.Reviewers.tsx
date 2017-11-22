import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import IconButton from "@material-ui/core/IconButton"
import AddIcon from "@material-ui/icons/Add"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import DetailsRow from "./Details.Row"
import UserChips from "./User.Chips"
import { getRelevantReviewersPerReview } from "../selectors/review"
import { useReview } from "../utils/ReviewContext"
import { useSelector } from "../store"

const useStyles = makeStyles((theme) => ({
  root: {
    "& button": { visibility: "hidden" },
    "&:hover button": {
      visibility: "visible",
    },
  },
  chip: { marginRight: "0.5rem" },
  empty: { display: "inline-block", fontStyle: "italic" },
  add: { marginLeft: theme.spacing(2) },
}))

type Props = {
  className?: string
}

const ReviewDetailsReviewers: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const reviewersPerReview = useSelector(getRelevantReviewersPerReview)
  const review = useReview()
  const reviewerIDs = reviewersPerReview.get(review.id)!
  const heading = reviewerIDs.size === 1 ? "Reviewer" : "Reviewers"
  const addButton = (
    <IconButton className={classes.add} size="small">
      <AddIcon />
    </IconButton>
  )
  if (reviewerIDs.size === 0)
    return (
      <DetailsRow heading={heading}>
        <Typography component="span" variant="body2" className={classes.empty}>
          No reviewers
        </Typography>
        {addButton}
      </DetailsRow>
    )
  return (
    <DetailsRow className={clsx(className, classes.root)} heading={heading}>
      <UserChips userIDs={reviewerIDs} />
      {addButton}
    </DetailsRow>
  )
}

export default Registry.add("Review.Details.Reviewers", ReviewDetailsReviewers)
