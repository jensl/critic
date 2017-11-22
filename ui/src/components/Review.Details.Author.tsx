import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import DetailsRow from "./Details.Row"
import UserChip from "./User.Chip"
import { useReview } from "../utils/ReviewContext"
import { map } from "../utils"

const useStyles = makeStyles({
  root: {},
  chip: { marginRight: "0.5rem" },
})

type OwnProps = {
  className?: string
}

const ReviewDetailsAuthor: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  const review = useReview()
  if (!review) return null
  const heading = review.owners.size === 1 ? "Author" : "Authors"
  const authors = map(review.owners, (userID) => (
    <UserChip key={userID} userID={userID} className={classes.chip} />
  ))
  return <DetailsRow heading={heading}>{authors}</DetailsRow>
}

export default Registry.add("Review.Details.Author", ReviewDetailsAuthor)
