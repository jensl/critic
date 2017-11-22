import React from "react"
import { RouteComponentProps } from "react-router"

import Registry from "."
import RepositoryDiff, { Params } from "./Repository.Diff"

const RepositoryBranchDiff: React.FunctionComponent<RouteComponentProps<
  Params
>> = (props) => {
  return <RepositoryDiff {...props} />
}

export default Registry.add("Repository.Branch.Diff", RepositoryBranchDiff)
