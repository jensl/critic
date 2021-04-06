import React, { useState, FunctionComponent } from "react"

import Alert from "@material-ui/lab/Alert"
import Button from "@material-ui/core/Button"
import Checkbox from "@material-ui/core/Checkbox"
import Dialog from "@material-ui/core/Dialog"
import DialogActions from "@material-ui/core/DialogActions"
import DialogContent from "@material-ui/core/DialogContent"
import DialogTitle from "@material-ui/core/DialogTitle"
import FormControlLabel from "@material-ui/core/FormControlLabel"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { discardUnpublishedChanges } from "../actions/batch"
import { useDialog, useReview } from "../utils"
import { useDispatch } from "../store"
import { useUnpublished } from "../utils/Batch"
import { DiscardItem } from "../actions"
import { filteredSet, mergedSets } from "../utils/Functions"

export const kDialogID = "discardChanges"

const useStyles = makeStyles((theme) => ({
  alert: {
    margin: theme.spacing(1, 0),
  },
  label: {
    display: "flex",
    marginLeft: theme.spacing(2),
  },
}))

type DiscardItemCheckboxProps = {
  label: string
  item: DiscardItem
}

type Props = {
  className?: string
}

const DiscardChanges: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const { isOpen, closeDialog } = useDialog(kDialogID)
  const review = useReview()
  const unpublished = useUnpublished()
  const [discardItems, setDiscardItems] = useState<ReadonlySet<DiscardItem>>(
    new Set(),
  )

  if (!unpublished) return null

  const callback = () => {
    const comment = (document.getElementById(
      `${kDialogID}-comment`,
    ) as HTMLInputElement | null)?.value
    return dispatch(discardUnpublishedChanges(review.id, [...discardItems]))
  }

  const handleChange = (...items: DiscardItem[]) => (
    ev: React.ChangeEvent<HTMLInputElement>,
  ) => {
    if (ev.target.checked)
      setDiscardItems((discardItems) => mergedSets(discardItems, items))
    else
      setDiscardItems((discardItems) =>
        filteredSet(discardItems, (current) => !items.includes(current)),
      )
  }

  const availableItems: DiscardItem[] = []

  if (unpublished.createdComments.length !== 0)
    availableItems.push("created_comments")
  if (unpublished.writtenReplies.length !== 0)
    availableItems.push("written_replies")
  if (unpublished.resolvedIssues.length !== 0)
    availableItems.push("resolved_issues")
  if (unpublished.reopenedIssues.length !== 0)
    availableItems.push("reopened_issues")
  if (unpublished.morphedComments.length !== 0)
    availableItems.push("morphed_comments")
  if (unpublished.reviewedChanges.length !== 0)
    availableItems.push("reviewed_changes")
  if (unpublished.unreviewedChanges.length !== 0)
    availableItems.push("unreviewed_changes")

  const DiscardItemCheckbox: FunctionComponent<DiscardItemCheckboxProps> = ({
    label,
    item,
  }) =>
    availableItems.includes(item) ? (
      <FormControlLabel
        className={classes.label}
        control={
          <Checkbox
            checked={discardItems.has(item)}
            onChange={handleChange(item)}
          />
        }
        label={label}
      />
    ) : null

  return (
    <Dialog className={className} open={isOpen} onClose={closeDialog}>
      <DialogTitle>Discard changes?</DialogTitle>
      <DialogContent>
        <Alert className={classes.alert} severity="warning">
          Discarding your unpublished changes deletes them permanently from the
          system.
        </Alert>
        {availableItems.length > 1 && (
          <FormControlLabel
            className={classes.label}
            control={
              <Checkbox
                checked={discardItems.size === availableItems.length}
                onChange={handleChange(...availableItems)}
              />
            }
            label={<em>Everything</em>}
          />
        )}
        <DiscardItemCheckbox label="Created comments" item="created_comments" />
        <DiscardItemCheckbox label="Written replies" item="written_replies" />
        <DiscardItemCheckbox label="Resolved issues" item="resolved_issues" />
        <DiscardItemCheckbox label="Reopened issues" item="reopened_issues" />
        <DiscardItemCheckbox label="Morphed comments" item="morphed_comments" />
        <DiscardItemCheckbox label="Reviewed changes" item="reviewed_changes" />
        <DiscardItemCheckbox
          label="Unreviewed changes"
          item="unreviewed_changes"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={closeDialog}>Do nothing</Button>
        <Button
          color="primary"
          disabled={discardItems.size === 0}
          variant="contained"
          onClick={() => callback().then(closeDialog)}
        >
          Discard changes
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default Registry.add("Dialog.Review.DiscardChanges", DiscardChanges)
