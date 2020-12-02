import React, { FunctionComponent, useState } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Edit from "./Review.Title.Edit"
import { isReviewOwner, useReview, useSignedInUser } from "../utils"

const useStyles = makeStyles((theme) => ({
  reviewTitle: { marginBottom: "11px", cursor: "pointer" },
  dropped: { textDecoration: "line-through" },
}))

type Props = {
  className?: string
}

const ReviewTitle: FunctionComponent<Props> = () => {
  const classes = useStyles()
  const review = useReview()
  const signedInUser = useSignedInUser()
  const [edit, setEdit] = useState(
    isReviewOwner(review, signedInUser) && !review?.summary?.trim(),
  )
  if (edit) return <Edit onEditDone={() => setEdit(false)} />
  return (
    <Typography
      className={clsx(classes.reviewTitle, {
        [classes.dropped]: review.state === "dropped",
      })}
      variant="h4"
      onClick={() => setEdit(true)}
    >
      {review.summary || <em>No review summary</em>}
    </Typography>
  )
}

export default Registry.add("Review.Title", ReviewTitle)
