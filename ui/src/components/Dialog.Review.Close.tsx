import React, { FunctionComponent } from "react"

import Typography from "@material-ui/core/Typography"

import Registry from "."
import Confirm from "./Dialog.Confirm"
import { closeReview } from "../actions/review"
import { useReview } from "../utils"
import { useDispatch } from "../store"

export const kDialogID = "closeReview"

type Props = {
  className?: string
}

const DropReview: FunctionComponent<Props> = ({ className }) => {
  const dispatch = useDispatch()
  const review = useReview()
  if (!review) return null
  return (
    <Confirm
      className={className}
      dialogID={kDialogID}
      title="Close review?"
      accept={{
        label: "Close review",
        callback: () => dispatch(closeReview(review.id)),
      }}
    >
      <Typography variant="body1">
        Closing a review marks it as finished, and removes it from all involved
        users' dashboards as it is no longer active.
      </Typography>
    </Confirm>
  )
}

export default Registry.add("Dialog.Review.Close", DropReview)
