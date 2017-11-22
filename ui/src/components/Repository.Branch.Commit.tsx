import React, { FunctionComponent } from "react"

import Registry from "."
import RepositoryCommit from "./Repository.Commit"
import { RouteComponentProps } from "react-router"

const RepositoryBranchCommit: FunctionComponent<RouteComponentProps<{
  ref: string
}>> = (props) => <RepositoryCommit {...props} />

export default Registry.add("Repository.Branch.Commit", RepositoryBranchCommit)
