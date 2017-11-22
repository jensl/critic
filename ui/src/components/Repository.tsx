import React from "react"
import {
  Switch,
  Route,
  Redirect,
  useRouteMatch,
  RouteComponentProps,
} from "react-router"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Paper from "@material-ui/core/Paper"
import Tab from "@material-ui/core/Tab"
import Tabs from "@material-ui/core/Tabs"
import Divider from "@material-ui/core/Divider"
import Container from "@material-ui/core/Container"

import Registry from "."
import RepositoryHeader from "./Repository.Header"
import RepositoryDetails from "./Repository.Details"
import RepositoryActions from "./Repository.Actions"
import RepositoryFiles from "./Repository.Files"
import { useRepository } from "../utils"

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
  activeTab: string
}

type Props = {
  className?: string
}

const Empty: React.FunctionComponent<RouteComponentProps> = ({ match }) => (
  <div>{match.path}</div>
)

const Repository: React.FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const { activeTab } = useRouteMatch<Params>().params
  const repository = useRepository()
  if (!repository) return null
  console.log({ repository })
  const prefix = `/repository/${repository.name}`
  if (!activeTab) return <Redirect to={`${prefix}/files`} />
  return (
    <>
      <Container className={clsx(className, classes.container)} maxWidth="lg">
        <RepositoryHeader />
        <Paper className={classes.paper}>
          <div className={classes.details}>
            <RepositoryDetails />
          </div>
          <div className={classes.actions}>
            <RepositoryActions />
          </div>
          <Divider />
          <Tabs
            className={classes.tabs}
            centered
            value={activeTab}
            indicatorColor="primary"
          >
            <Tab
              component={Link}
              to={`${prefix}/files`}
              value="files"
              label="Files"
            />
            <Tab
              component={Link}
              to={`${prefix}/branches`}
              value="branches"
              label="Branches"
            />
          </Tabs>
          <Switch>
            <Route path={`${prefix}/files`} component={RepositoryFiles} />
            <Route path={`${prefix}/branches`} component={Empty} />
          </Switch>
        </Paper>
      </Container>
    </>
  )
}

export default Registry.add("Repository", Repository)
