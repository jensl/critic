import React, { FunctionComponent, useRef, useState } from "react"

import Button from "@material-ui/core/Button"
import Dialog from "@material-ui/core/Dialog"
import DialogActions from "@material-ui/core/DialogActions"
import DialogContent from "@material-ui/core/DialogContent"
import DialogTitle from "@material-ui/core/DialogTitle"
import FormControl from "@material-ui/core/FormControl"
import FormControlLabel from "@material-ui/core/FormControlLabel"
import FormLabel from "@material-ui/core/FormLabel"
import Radio from "@material-ui/core/Radio"
import RadioGroup from "@material-ui/core/RadioGroup"
import Alert from "@material-ui/lab/Alert"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import {
  useReview,
  Value,
  useValue,
  useChangeset,
  useResource,
  useSignedInUser,
} from "../utils"
import { useDispatch } from "../store"
import { longestCommonPathPrefix } from "../utils/Strings"
import { assertNotNull } from "../debug"
import { ReviewFilterInput, createReviewFilters } from "../actions/reviewfilter"
import { FileID } from "../resources/types"

export const kDialogID = "createBranch"

const ErrorMessage = new Value<string | null>(
  "AssignChanges/errorMessage",
  null,
)

const useStyles = makeStyles((theme) => ({
  reason: {
    marginBottom: theme.spacing(2),
  },
  path: {
    ...theme.critic.monospaceFont,
    ...theme.critic.standout,
  },
}))

export type AssignChangesReason = "nothing-assigned" | "something-unassigned"
export type AssignChangesMode = "all" | "prefix" | "files"

type DialogProps = {
  open: boolean
  onClose: () => void
}
type ReasonProp = {
  reason: AssignChangesReason
}
type FileIDProp = {
  fileID: FileID
}
type Props = DialogProps & (ReasonProp | FileIDProp)

const AssignChanges: FunctionComponent<Props> = ({
  open,
  onClose,
  ...props
}) => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const signedInUser = useSignedInUser()
  const review = useReview()
  const { changeset } = useChangeset()
  const filesByID = useResource("files", ({ byID }) => byID)
  const [mode, setMode] = useState<AssignChangesMode | null>(null)

  const paths =
    changeset.files?.map((fileID) => filesByID.get(fileID)?.path ?? "") ?? []
  const prefix = longestCommonPathPrefix(paths)

  if (!signedInUser || !review) return null

  const reason = "reason" in props ? props.reason : null
  const path =
    "fileID" in props ? filesByID.get(props.fileID)?.path ?? null : null

  const assignChanges = mode
    ? async () => {
        const reviewFilters: ReviewFilterInput[] = []
        const reviewFilter = (path: string): ReviewFilterInput => ({
          subject: signedInUser.id,
          type: "reviewer",
          review: review.id,
          path,
        })
        switch (mode) {
          case "all":
            reviewFilters.push(reviewFilter(""))
            break
          case "prefix":
            assertNotNull(prefix)
            reviewFilters.push(reviewFilter(prefix))
            break
          case "files":
            reviewFilters.push(...paths.map(reviewFilter))
            break
        }
        await dispatch(createReviewFilters(reviewFilters))
        onClose()
      }
    : () => null

  return (
    <Dialog open={open}>
      <DialogTitle>Assign changes</DialogTitle>
      <DialogContent>
        {reason === "nothing-assigned" && (
          <Alert className={classes.reason} severity="info">
            You are currently not assigned to review any of these changes.
          </Alert>
        )}
        {reason === "something-unassigned" && (
          <Alert className={classes.reason} severity="info">
            You are currently not assigned to review all of these changes.
          </Alert>
        )}
        {path !== null && (
          <Alert className={classes.reason} severity="info">
            You are currently not assigned to review the changes in this file.
          </Alert>
        )}
        <FormControl component="fieldset">
          <FormLabel component="legend">Assign all changes...</FormLabel>
          <RadioGroup
            onChange={(ev) => setMode(ev.target.value as AssignChangesMode)}
          >
            <FormControlLabel
              value="all"
              label="in the review"
              control={<Radio />}
            />
            {prefix && (
              <FormControlLabel
                value="prefix"
                label={
                  <>
                    in the directory{" "}
                    <span className={classes.path}>{prefix}</span>
                  </>
                }
                control={<Radio />}
              />
            )}
            {path !== null ? (
              <FormControlLabel
                value="files"
                label={
                  <>
                    in <span className={classes.path}>{path}</span>
                  </>
                }
                control={<Radio />}
              />
            ) : paths.length > 1 ? (
              <FormControlLabel
                value="files"
                label={<>in these {paths.length} files</>}
                control={<Radio />}
              />
            ) : (
              paths.length === 1 && (
                <FormControlLabel
                  value="files"
                  label={
                    <>
                      in <span className={classes.path}>{paths[0]}</span>
                    </>
                  }
                  control={<Radio />}
                />
              )
            )}
          </RadioGroup>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Do nothing</Button>
        <Button disabled={mode === null} onClick={assignChanges}>
          Assign as reviewer
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default Registry.add("Dialog.Review.AssignChanges", AssignChanges)
