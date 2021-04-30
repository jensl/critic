import React, { FunctionComponent, useRef } from "react"

import Button from "@material-ui/core/Button"
import Dialog from "@material-ui/core/Dialog"
import DialogActions from "@material-ui/core/DialogActions"
import DialogContent from "@material-ui/core/DialogContent"
import DialogTitle from "@material-ui/core/DialogTitle"
import Typography from "@material-ui/core/Typography"
import TextField from "@material-ui/core/TextField"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { setBranch } from "../actions/review"
import {
  useDialog,
  useReview,
  Value,
  useValue,
  useSignedInUser,
} from "../utils"
import { useDispatch } from "../store"
import { handleError } from "../resources"

export const kDialogID = "createBranch"

const ErrorMessage = new Value<string | null>("CreateBranch/errorMessage", null)

const useStyles = makeStyles((theme) => ({
  branchName: {},
}))

const filterSummary = (summary: string) =>
  summary
    .replace(/[^\w\d]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase()

const CreateBranch: FunctionComponent = () => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const review = useReview()
  const user = useSignedInUser()
  const { isOpen, closeDialog } = useDialog(kDialogID)
  const [errorMessage, setErrorMessage] = useValue(ErrorMessage)
  const branchName = useRef<HTMLInputElement>(null)
  if (!user || !review) return null
  const createBranch = async () => {
    if (!branchName.current) return
    await dispatch(
      setBranch(
        review.id,
        branchName.current.value.trim(),
        handleError(
          "BAD_BRANCH_NAME",
          (error) => void setErrorMessage(error.message),
        ),
      ),
    )
    closeDialog()
  }
  const defaultValue = () => {
    if (review.summary) {
      return `r/${user.name}/${filterSummary(review.summary)}`
    }
    return ""
  }
  return (
    <Dialog open={isOpen} onClose={closeDialog}>
      <DialogTitle>Create branch</DialogTitle>
      <DialogContent>
        <Typography variant="body1">
          This operation will merely create a branch in the repository, pointing
          at the commits that are already there. No new commits will be created
          or pushed to any new location.
        </Typography>
        <TextField
          inputRef={branchName}
          className={classes.branchName}
          label="Branch name"
          margin="normal"
          error={typeof errorMessage === "string"}
          helperText={errorMessage}
          defaultValue={defaultValue()}
          fullWidth
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={closeDialog}>Do nothing</Button>
        <Button onClick={createBranch}>Create branch</Button>
      </DialogActions>
    </Dialog>
  )
}

export default Registry.add("Dialog.Review.CreateBranch", CreateBranch)