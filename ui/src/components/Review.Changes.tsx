import React, { FunctionComponent } from "react"

import Registry from "."
import ChangesetContext from "./Changeset.Context"
import { loadAutomaticChangeset } from "../actions/changeset"
import { useReview, useSubscription } from "../utils"
import Changeset from "./Changeset"
import { useSelector } from "../store"

const ReviewChanges: FunctionComponent = () => {
  const review = useReview()
  const changesets = useSelector((state) => state.resource.changesets)
  useSubscription(loadAutomaticChangeset, "everything", review.id)
  const changesetID = changesets.automatic.get(`${review.id}:everything`) ?? -1
  const changeset = changesets.byID.get(changesetID)
  if (!changeset) return null
  return (
    <ChangesetContext changeset={changeset}>
      <Changeset variant="unified" />
    </ChangesetContext>
  )
}

export default Registry.add("Review.Changes", ReviewChanges)
