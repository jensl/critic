import React, { FunctionComponent } from "react"

import Alert from "@material-ui/lab/Alert"
import AlertTitle from "@material-ui/lab/AlertTitle"
import TextField from "@material-ui/core/TextField"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Confirm from "./Dialog.Confirm"
import { createBatch } from "../actions/batch"
import { useReview } from "../utils"
import { useDispatch } from "../store"
import { useReviewTags } from "../utils/ReviewTag"

export const kDialogID = "publishChanges"

const useStyles = makeStyles((theme) => ({
  alert: {
    margin: theme.spacing(1, 0),
  },
}))

type Props = {
  className?: string
}

const PublishChanges: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const review = useReview()
  const tags = useReviewTags()

  const callback = () => {
    const comment = (document.getElementById(
      `${kDialogID}-comment`,
    ) as HTMLInputElement | null)?.value
    return dispatch(createBatch(review.id, comment))
  }

  return (
    <Confirm
      className={className}
      dialogID={kDialogID}
      title="Publish changes?"
      accept={{ label: "Publish changes", callback }}
    >
      {tags.has("would_be_accepted") ? (
        <Alert className={classes.alert} severity="success">
          <AlertTitle>Accepted</AlertTitle>
          With these changes published, the review will be accepted.
        </Alert>
      ) : tags.has("would_be_unaccepted") ? (
        <Alert className={classes.alert} severity="warning">
          With these changes published, the review will NO LONGER be accepted.
        </Alert>
      ) : (
        <Alert className={classes.alert} severity="info">
          Publishing your changes makes them visible to other users.
        </Alert>
      )}
      <TextField
        id={`${kDialogID}-comment`}
        label="Comment"
        placeholder="Explain yourself, or write something nice!"
        fullWidth
        multiline
      />
    </Confirm>
  )
}

export default Registry.add("Dialog.Review.PublishChanges", PublishChanges)
