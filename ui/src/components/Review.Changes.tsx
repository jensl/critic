import React, { FunctionComponent, useEffect } from "react"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import ChangesetContext from "./Changeset.Context"
import { loadAutomaticChangeset } from "../actions/changeset"
import {
  useResource,
  useReview,
  useSubscription,
  useValue,
  Value,
} from "../utils"
import Changeset from "./Changeset"
import { useSelector } from "../store"
import {
  AutomaticMode,
  AutomaticChangesetEmpty,
  AutomaticChangesetImpossible,
} from "../actions"
import { useHistory, useParams } from "react-router"

const parseModeParam = (
  value: string | undefined,
  defaultValue: AutomaticMode,
): AutomaticMode => {
  switch (value) {
    case "everything":
    case "pending":
      return value

    default:
      return defaultValue
  }
}

const ReviewChanges: FunctionComponent = () => {
  const { mode: modeParam } = useParams<{ mode?: string }>()
  const automaticMode = parseModeParam(modeParam, "everything")

  const history = useHistory()
  const review = useReview()
  const changesets = useSelector((state) => state.resource.changesets)
  const automaticResult = useResource("changesets", ({ automatic }) =>
    automatic.get(`${review.id}:${automaticMode}`),
  )

  const setAutomaticMode = (mode: AutomaticMode) => {
    history.push(`/review/${review.id}/changes/${mode}`)
  }

  useSubscription(loadAutomaticChangeset, automaticMode, review.id)
  useEffect(() => {
    if (
      automaticMode !== "everything" &&
      (automaticResult instanceof AutomaticChangesetEmpty ||
        automaticResult instanceof AutomaticChangesetImpossible)
    )
      setAutomaticMode("everything")
  }, [automaticMode, automaticResult])

  const changesetID = changesets.automatic.get(`${review.id}:${automaticMode}`)
  if (typeof changesetID !== "number") return null
  const changeset = changesets.byID.get(changesetID)
  if (!changeset) return null

  return (
    <ChangesetContext changeset={changeset}>
      <Changeset
        variant="unified"
        integrated
        automaticMode={automaticMode}
        setAutomaticMode={setAutomaticMode}
      />
    </ChangesetContext>
  )
}

export default Registry.add("Review.Changes", ReviewChanges)
