import React from "react"
import { Switch, Route, Redirect, useRouteMatch } from "react-router"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Paper from "@material-ui/core/Paper"
import Tab from "@material-ui/core/Tab"
import Tabs from "@material-ui/core/Tabs"
import Divider from "@material-ui/core/Divider"
import Container from "@material-ui/core/Container"

import Registry from "."
import Header from "./Branch.Header"
import Details from "./Branch.Details"
import RepositoryCommit from "./Repository.Commit"
import RepositoryDiff from "./Repository.Diff"
import Commits from "./Branch.Commits"
import BranchFiles from "./Branch.Files"
import Settings from "./Branch.Settings"
import SetPrefix, { usePrefix } from "../utils/PrefixContext"
import { id, useRepository, useResource, useSubscription } from "../utils"
import SetBranch from "../utils/BranchContext"
import Breadcrumb from "./Breadcrumb"
import { loadBranchByName } from "../actions/branch"

const useStyles = makeStyles((theme) => ({
  container: {
    [theme.breakpoints.down("sm")]: {
      paddingLeft: theme.spacing(1),
      paddingRight: theme.spacing(1),
    },
  },

  paper: {
    marginTop: "1rem",
    paddingTop: theme.spacing(2),
    paddingBottom: theme.spacing(2),
    paddingLeft: theme.spacing(3),
    paddingRight: theme.spacing(3),

    [theme.breakpoints.down("sm")]: {
      paddingLeft: theme.spacing(1),
      paddingRight: theme.spacing(1),
    },
  },

  details: {},
  actions: {},

  tabs: {
    marginBottom: theme.spacing(1),
  },
}))

type Params = {
  branchName: string
  activeTab?: string
}

type Props = {
  className?: string
}

const Display: React.FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const { activeTab } = useRouteMatch<Params>().params
  const prefix = usePrefix()
  if (!activeTab) return <Redirect to={`${prefix}/commits`} />
  return (
    <Container className={clsx(className, classes.container)} maxWidth="lg">
      <Header />
      <Paper className={classes.paper}>
        <div className={classes.details}>
          <Details />
        </div>
        {/* <div className={classes.actions}>
            <RepositoryActions />
          </div> */}
        <Divider />
        <Tabs
          className={classes.tabs}
          centered
          value={activeTab}
          indicatorColor="primary"
        >
          <Tab
            component={Link}
            to={`${prefix}/commits`}
            value="commits"
            label="Commits"
          />
          <Tab
            component={Link}
            to={`${prefix}/files`}
            value="files"
            label="Files"
          />
          <Tab
            component={Link}
            to={`${prefix}/settings`}
            value="settings"
            label="Settings"
          />
        </Tabs>
        <Switch>
          <Route path={`${prefix}/commits`} component={Commits} />
          <Route path={`${prefix}/files`} component={BranchFiles} />
          <Route path={`${prefix}/settings/:section?`} component={Settings} />
        </Switch>
      </Paper>
    </Container>
  )
}

const Branch: React.FunctionComponent<Props> = ({ className }) => {
  const { branchName } = useRouteMatch<Params>().params
  const repository = useRepository()
  const branch = useResource("branches", ({ byID, byName }) =>
    byID.get(byName.get(`${repository.id}:${branchName}`) ?? -1),
  )
  useSubscription(loadBranchByName, [repository.id, branchName])
  const parentPrefix = usePrefix()
  if (!branch) return null
  const prefix = `${parentPrefix}/branch/${branchName}/-`
  return (
    <Breadcrumb
      category="branch"
      label={branch.name}
      path={`${parentPrefix}/branch/${branchName}`}
    >
      <SetPrefix prefix={prefix}>
        <SetBranch branch={branch}>
          <Switch>
            <Route
              path={`${prefix}/commit/:ref`}
              component={RepositoryCommit}
            />
            <Route
              path={`${prefix}/diff/:from([0-9a-f]{4,40}\\^*)..:to([0-9a-f]{4,40})`}
              component={RepositoryDiff}
            />
            <Route component={Display} />
          </Switch>
        </SetBranch>
      </SetPrefix>
    </Breadcrumb>
  )
}

export default Registry.add("Branch", Branch)
