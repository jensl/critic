import React from "react"
import { Switch, Route, useRouteMatch } from "react-router-dom"

import Registry from "."
import RepositoryBranchCommit from "./Repository.Branch.Commit"
import RepositoryBranchCommits from "./Repository.Branch.Commits"
import RepositoryBranchDiff from "./Repository.Branch.Diff"
import Breadcrumb from "./Breadcrumb"
import { loadBranchByName } from "../actions/branch"
import {
  useRepository,
  useSubscription,
  useResource,
  usePrefix,
} from "../utils"
import { SetBranch } from "../utils/BranchContext"
import Branch from "./Branch"

type Params = {
  name: string
}

const RepositoryBranch: React.FunctionComponent = () => {
  const prefix = usePrefix()
  return (
    <Breadcrumb label="branches" path={`${prefix}/branches`}>
      <Branch />
      {/* <Breadcrumb category="branch" label={branch.name} path={branchPrefix}>
        <SetBranch branch={branch}>
          <Switch>
            <Route
              path={`${branchPrefix}/commit/:ref`}
              component={RepositoryBranchCommit}
            />
            <Route
              path={`${branchPrefix}/diff/:from([0-9a-f]{4,40}\\^*)..:to([0-9a-f]{4,40})`}
              component={RepositoryBranchDiff}
            />
            <Route component={RepositoryBranchCommits} />
          </Switch>
        </SetBranch>
      </Breadcrumb> */}
    </Breadcrumb>
  )
}

export default Registry.add("Repository.Branch", RepositoryBranch)
