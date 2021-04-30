import React, { FunctionComponent } from "react"

import Registry from "."
import LoaderBlock from "./Loader.Block"
import ChangesetSingleCommit from "./Changeset.SingleCommit"
import Breadcrumb from "./Breadcrumb"
import { resolveRef } from "../actions/commit"
import { useRepository, useSubscription } from "../utils"
import { useRouteMatch } from "react-router"
import { assertNotReached } from "../debug"
import { useSelector } from "../store"

type Params = {
  ref: string
}

const RepositoryCommit: FunctionComponent = () => {
  const repository = useRepository()!
  const commits = useSelector((state) => state.resource.commits)
  const commitRefs = useSelector((state) => state.resource.extra.commitRefs)
  const { ref } = useRouteMatch<Params>().params
  useSubscription(resolveRef, [ref, repository.id])
  const commitID = commitRefs.get(`${repository.id}:${ref}`)
  if (commitID === null)
    return <LoaderBlock waitingFor={`Resolving commit ref: ${ref}`} />
  // FIXME: This is an input error; output an error message.
  if (typeof commitID !== "number") return null
  const commit = commits.byID.get(commitID)
  if (!commit) {
    assertNotReached("resolveRef() should have loaded the commit")
    return null
  }
  return (
    <Breadcrumb category="commit" label={commit.sha1.substring(0, 8)}>
      <ChangesetSingleCommit commit={commit} />
    </Breadcrumb>
  )
}

export default Registry.add("Repository.Commit", RepositoryCommit)
