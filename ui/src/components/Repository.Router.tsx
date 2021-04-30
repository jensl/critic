import React, { FunctionComponent } from "react"
import { Switch, Route, RouteComponentProps } from "react-router-dom"
import pathToRegexp from "path-to-regexp"

import Registry from "."
import Breadcrumb from "./Breadcrumb"
import Repository from "./Repository"
import RepositoryBranch from "./Repository.Branch"
import RepositoryCommit from "./Repository.Commit"
import RepositoryDiff from "./Repository.Diff"
import RepositoryReview from "./Repository.Review"
import { loadRepositoryByName } from "../actions/repository"
import { useSubscription, useResource } from "../utils"
import SetRepository from "../utils/RepositoryContext"
import SetPrefix from "../utils/PrefixContext"

type Params = { name: string }

const RepositoryRouter: FunctionComponent<RouteComponentProps<Params>> = ({
  match,
}) => {
  const { name } = match.params
  useSubscription(loadRepositoryByName, [name])
  const repository = useResource("repositories", ({ byID, byName }) =>
    byID.get(byName.get(name) ?? -1),
  )
  if (!repository) return null
  const prefix = `/repository/${repository.name}`
  return (
    <SetRepository repository={repository}>
      <SetPrefix prefix={prefix}>
        <Breadcrumb category="repository" label={repository.path} path={prefix}>
          <Switch>
            <Route
              path={`${prefix}/commit/:ref`}
              component={RepositoryCommit}
            />
            <Route
              path={`${prefix}/branch/:branchName*/-/:activeTab?`}
              component={RepositoryBranch}
            />
            <Route
              path={`${prefix}/branch/:branchName*`}
              component={RepositoryBranch}
            />
            <Route
              path={`${prefix}/review/:reviewID/:activeTab?`}
              component={RepositoryReview}
            />
            <Route
              path={`${prefix}/diff/:from([0-9a-f]{4,40}\\^*)..:to([0-9a-f]{4,40})`}
              component={RepositoryDiff}
            />
            <Route path={`${prefix}/:activeTab?`} component={Repository} />
          </Switch>
        </Breadcrumb>
      </SetPrefix>
    </SetRepository>
  )
}

export default Registry.add("Repository.Router", RepositoryRouter)
