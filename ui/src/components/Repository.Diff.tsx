import React, { FunctionComponent } from "react"
import { useParams } from "react-router"

import Registry from "."
import ChangesetRange from "./Changeset.Range"

export type Params = {
  from: string
  to: string
}

const RepositoryDiff: FunctionComponent = () => {
  const { from: fromCommitRef, to: toCommitRef } = useParams<Params>()
  return (
    <ChangesetRange fromCommitRef={fromCommitRef} toCommitRef={toCommitRef} />
  )
}

export default Registry.add("Repository.Diff", RepositoryDiff)
