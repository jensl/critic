import React, { FunctionComponent } from "react"
import { useParams } from "react-router"

import Registry from "."
import Breadcrumb from "./Breadcrumb"
import ChangesetContext from "./Changeset.Context"
import { loadChangesetBySHA1 } from "../actions/changeset"
import {
  useRepository,
  useSubscription,
  useReview,
  id,
  useResource,
  useResourceExtra,
} from "../utils"
import Changeset from "./Changeset"

export type Params = {
  from: string
  to: string
}

const nullBecause = (reason: string) => {
  console.log("RepositoryDiff returning null: ", { reason })
  return null
}

const RepositoryDiff: FunctionComponent = () => {
  const { from: fromCommitRef, to: toCommitRef } = useParams<Params>()
  const { id: repositoryID } = useRepository()!
  const review = useReview()
  useSubscription(loadChangesetBySHA1, {
    fromCommitRef,
    toCommitRef,
    repositoryID,
    reviewID: id(review),
  })
  const changesets = useResource("changesets")
  const commits = useResource("commits")
  const commitRefs = useResourceExtra("commitRefs")

  const fromCommitID = commitRefs.get(`${repositoryID}:${fromCommitRef}`)
  if (typeof fromCommitID !== "number")
    return nullBecause(
      `no fromCommitID: "${repositoryID}:${fromCommitRef}" not in commitRefs`
    )
  const fromCommit = commits.byID.get(fromCommitID)
  if (!fromCommit)
    return nullBecause(`no fromCommit: ${fromCommitID} not in commits.byID`)
  const toCommitID = commitRefs.get(`${repositoryID}:${toCommitRef}`)
  if (typeof toCommitID !== "number")
    return nullBecause(
      `no toCommitID: "${repositoryID}:${toCommitRef}" not in commitRefs`
    )
  const toCommit = commits.byID.get(toCommitID)
  if (!toCommit)
    return nullBecause(`no toCommit: ${toCommitID} not in commits.byID`)
  const changesetID = changesets.byCommits.get(
    `${fromCommit.id}..${toCommit.id}`
  )
  if (typeof changesetID !== "number")
    return nullBecause(
      `no changesetID: ${fromCommit.id}..${toCommit.id} not in changesets.byCommits`
    )
  const changeset = changesets.byID.get(changesetID)
  if (!changeset)
    return nullBecause(`no changeset: ${changesetID} not in changesets.byID`)
  const fromSHA1 = fromCommit.sha1.substring(0, 8)
  const toSHA1 = toCommit.sha1.substring(0, 8)
  console.log("RepositoryDiff found changeset")
  return (
    <Breadcrumb category="diff" label={`${fromSHA1}..${toSHA1}`}>
      <ChangesetContext changeset={changeset}>
        <Changeset />
      </ChangesetContext>
    </Breadcrumb>
  )
}

export default Registry.add("Repository.Diff", RepositoryDiff)
