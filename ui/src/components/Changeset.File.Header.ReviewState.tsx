import React, { FunctionComponent, useState } from "react"
import clsx from "clsx"

import Alert from "@material-ui/lab/Alert"
import Checkbox from "@material-ui/core/Checkbox"
import Snackbar from "@material-ui/core/Snackbar"
import Tooltip from "@material-ui/core/Tooltip"
import Typography from "@material-ui/core/Typography"
import CheckIcon from "@material-ui/icons/Check"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import AssignChanges from "./Dialog.Review.AssignChanges"
import ReviewableFileChange from "../resources/reviewablefilechange"
import { all, any, map, useOptionalReview, useSignedInUser } from "../utils"
import { useDispatch } from "../store"
import { setIsReviewed } from "../actions/reviewableFilechange"
import { filteredSet, mergedSets } from "../utils/Functions"
import UserChips from "./User.Chips"
import File from "../resources/file"
import { useRequireSession } from "./Dialog.SignIn"

const useStyles = makeStyles((theme) => ({
  reviewState: {
    display: "flex",
    flexDirection: "row",
  },
  iconContainer: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    marginRight: theme.spacing(1),
  },
  checkIcon: { alignSelf: "flex-end" },
  checkIconReviewed: { color: theme.palette.success.main },
  checkbox: { padding: 0 },
  usersInTooltip: { display: "flex", flexDirection: "column" },
}))

type Props = {
  className?: string
  file: File
  rfcs: ReadonlySet<ReviewableFileChange> | null
}

const ReviewState: FunctionComponent<Props> = ({ className, file, rfcs }) => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const signedInUser = useSignedInUser()
  const review = useOptionalReview()
  const [requireSession, signInDialog] = useRequireSession(
    "You need to sign in before you can mark changes as reviewed.",
  )
  const [assignChanges, setAssignChanges] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  if (!review || rfcs === null) return null

  const isReviewed = all(rfcs, (rfc) => rfc.isReviewed)
  const isReviewedByOtherUsers = signedInUser
    ? any(rfcs, (rfc) =>
        rfc.reviewedBy.size === 1
          ? !rfc.reviewedBy.has(signedInUser.id)
          : rfc.reviewedBy.size > 1,
      )
    : any(rfcs, (rfc) => rfc.reviewedBy.size !== 0)
  const isReviewedBySignedInUser =
    !!signedInUser && all(rfcs, (rfc) => rfc.isReviewedBy(signedInUser.id))
  const otherReviewers = mergedSets(...map(rfcs, (rfc) => rfc.reviewedBy))
  const assignedFiles = signedInUser
    ? filteredSet(rfcs, (rfc) => rfc.assignedReviewers.has(signedInUser.id))
    : new Set()

  const onToggle = async (value: boolean) => {
    if (review.state === "open") {
      if (await requireSession()) {
        if (assignedFiles.size !== 0) await dispatch(setIsReviewed(rfcs, value))
        else setAssignChanges(true)
      }
    } else if (review.state === "draft") {
      setMessage(`The review has not been published yet!`)
    } else {
      setMessage(`The review is ${review.state}!`)
    }
  }

  return (
    <span
      className={clsx(className, classes.reviewState)}
      onMouseDown={(ev) => ev.stopPropagation()}
    >
      {isReviewedByOtherUsers && (
        <span className={classes.iconContainer}>
          <Tooltip
            title={
              <>
                <Typography variant="body2">Reviewed by: </Typography>
                <UserChips
                  className={classes.usersInTooltip}
                  userIDs={otherReviewers}
                />
              </>
            }
          >
            <CheckIcon
              className={clsx(
                classes.checkIcon,
                isReviewed && classes.checkIconReviewed,
              )}
            />
          </Tooltip>
        </span>
      )}
      <Checkbox
        onMouseDown={(ev) => ev.stopPropagation()}
        onClick={(ev) => onToggle((ev.target as HTMLInputElement).checked)}
        checked={isReviewedBySignedInUser}
        className={clsx(className, classes.checkbox)}
        color="primary"
      />
      {signInDialog}
      {assignChanges && (
        <AssignChanges
          open
          onClose={() => setAssignChanges(false)}
          fileID={file.id}
        />
      )}
      {message && (
        <Snackbar open autoHideDuration={5000} onClose={() => setMessage(null)}>
          <Alert severity="error" variant="filled">
            {message}
          </Alert>
        </Snackbar>
      )}
    </span>
  )
}

export default Registry.add("Changeset.File.Header.ReviewState", ReviewState)
