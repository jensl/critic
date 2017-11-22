import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import UserListItem from "./User.ListItem"
import Review from "../resources/review"
import { map } from "../utils"

const useStyles = makeStyles({
  reviewListItemMetadata: {
    gridArea: "metadata",
    opacity: 0.5,
  },
})

type OwnProps = {
  className?: string
  review: Review
}

const ReviewListItemMetadata: FunctionComponent<OwnProps> = ({
  className,
  review,
}) => {
  const classes = useStyles()
  return (
    <Typography className={clsx(className, classes.reviewListItemMetadata)}>
      by{" "}
      {map(review.owners, (userID) => (
        <UserListItem key={userID} userID={userID} />
      ))}
    </Typography>
  )
}

export default Registry.add("Review.ListItem.Metadata", ReviewListItemMetadata)
