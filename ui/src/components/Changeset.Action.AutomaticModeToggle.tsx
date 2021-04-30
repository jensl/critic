import React from "react"
import clsx from "clsx"

import Switch from "@material-ui/core/Switch"
import Tooltip from "@material-ui/core/Tooltip"
import Typography from "@material-ui/core/Typography"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { ActionProps } from "./Changeset.Action"
import { id, useResource, useOptionalReview } from "../utils"
import {
  AutomaticChangesetEmpty,
  AutomaticChangesetImpossible,
  AutomaticMode,
} from "../actions"
import { loadAutomaticChangeset } from "../actions/changeset"
import { AsyncThunk } from "../state"
import { useDispatch } from "../store"

const useStyles = makeStyles({
  disabled: {
    opacity: 0.5,
  },
})

const AutomaticModeToggle: React.FunctionComponent<ActionProps> = ({
  automaticMode,
  setAutomaticMode,
}) => {
  const classes = useStyles()
  const review = useOptionalReview()
  const dispatch = useDispatch()
  const pending = useResource("changesets", ({ automatic }) =>
    automatic.get(`${id(review)}:pending`),
  )
  if (!review || !automaticMode || !setAutomaticMode) return null
  let disabled = false
  let pendingMessage
  if (
    pending instanceof AutomaticChangesetEmpty ||
    pending instanceof AutomaticChangesetImpossible
  ) {
    disabled = true
    if (pending instanceof AutomaticChangesetImpossible)
      pendingMessage = `Impossible: ${pending.message}`
    else pendingMessage = `Empty: ${pending.message}`
  } else {
    pendingMessage = "Display changes you have not reviewed yet."
  }

  const toggle = (mode: AutomaticMode): AsyncThunk<void> => async (
    dispatch,
    getState,
  ) => {
    if (!getState().resource.changesets.automatic.get(`${review.id}:${mode}`))
      console.log(await dispatch(loadAutomaticChangeset(mode, review.id)))
    setAutomaticMode(mode)
  }

  return (
    <Typography variant="body1">
      Everything
      <Switch
        checked={automaticMode === "pending"}
        disabled={disabled}
        onChange={(_, value) =>
          dispatch(toggle(value ? "pending" : "everything"))
        }
      />
      <Tooltip title={pendingMessage}>
        <span className={clsx(disabled && classes.disabled)}>Pending</span>
      </Tooltip>
    </Typography>
  )
}

export default Registry.add(
  "Changeset.Action.AutomaticModeToggle",
  AutomaticModeToggle,
)
