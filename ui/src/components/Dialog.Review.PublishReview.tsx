import React, { FunctionComponent } from "react"

import Typography from "@material-ui/core/Typography"

import Registry from "."
import Confirm from "./Dialog.Confirm"
import { publishReview } from "../actions/review"
import { useReview } from "../utils"
import { useDispatch } from "../store"

export const kDialogID = "publishReview"

type Props = {
  className?: string
}

const PublishReview: FunctionComponent<Props> = ({ className }) => {
  const dispatch = useDispatch()
  const review = useReview()
  if (!review) return null
  return (
    <Confirm
      className={className}
      dialogID={kDialogID}
      title="Publish review?"
      accept={{
        label: "Publish review",
        callback: () => dispatch(publishReview(review.id)),
      }}
    >
      <Typography variant="body1">
        Publishing a review sends out email notifications to involved users
        (e.g. reviewers) alerting them to the review's existance, and makes it
        appear on their dashboards.
      </Typography>
    </Confirm>
  )
}

export default Registry.add("Dialog.Review.PublishReview", PublishReview)
