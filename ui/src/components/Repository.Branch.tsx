import React from "react"
import { Switch, Route, useRouteMatch } from "react-router-dom"

import Registry from "."
import RepositoryBranchCommit from "./Repository.Branch.Commit"
import RepositoryBranchCommits from "./Repository.Branch.Commits"
import RepositoryBranchDiff from "./Repository.Branch.Diff"
import Breadcrumb from "./Breadcrumb"
import { loadBranch } from "../actions/branch"
import { useRepository, useSubscription, useResource } from "../utils"
import { SetBranch } from "../utils/BranchContext"

type Params = {
  name: string
}

const RepositoryBranch: React.FunctionComponent = () => {
  const branches = useResource("branches")
  const {
    params: { name },
  } = useRouteMatch<Params>()
  const { id: repositoryID, name: repositoryName } = useRepository()!
  useSubscription(loadBranch, { repositoryID, name })
  const branchID = branches.byName.get(`${repositoryID}:${name}`) ?? -1
  const branch = branches.byID.get(branchID)
  if (!branch) return null
  const prefix = `/repository/${repositoryName}/branch/${branch.name}`
  return (
    <Breadcrumb category="branch" label={branch.name} path={prefix}>
      <SetBranch branch={branch}>
        <Switch>
          <Route
            path={`${prefix}/commit/:ref`}
            component={RepositoryBranchCommit}
          />
          <Route
            path={`${prefix}/diff/:from([0-9a-f]{4,40}\\^*)..:to([0-9a-f]{4,40})`}
            component={RepositoryBranchDiff}
          />
          <Route component={RepositoryBranchCommits} />
        </Switch>
      </SetBranch>
    </Breadcrumb>
  )
}

export default Registry.add("Repository.Branch", RepositoryBranch)
