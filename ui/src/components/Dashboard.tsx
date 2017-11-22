import React, { FunctionComponent } from "react"
import { Redirect, Route, Switch, RouteComponentProps } from "react-router"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Container from "@material-ui/core/Container"
import Paper from "@material-ui/core/Paper"
import Tab from "@material-ui/core/Tab"
import Tabs from "@material-ui/core/Tabs"

import Registry from "."
import Branches from "./Dashboard.Branches"
import Incoming from "./Dashboard.Incoming"
import Outgoing from "./Dashboard.Outgoing"

const useStyles = makeStyles((theme) => ({
  dashboard: {},
  paper: {
    marginTop: "1rem",
    paddingTop: theme.spacing(2),
    paddingBottom: theme.spacing(2),
    paddingLeft: theme.spacing(3),
    paddingRight: theme.spacing(3),
  },
}))

type Params = {
  activeTab: string
}

type OwnProps = {
  className?: string
}

const Dashboard: FunctionComponent<OwnProps & RouteComponentProps<Params>> = ({
  className,
  match,
}) => {
  const classes = useStyles()
  const { activeTab } = match.params
  if (!activeTab) return <Redirect to={"/dashboard/incoming"} />
  return (
    <Container maxWidth="lg" className={clsx(className, classes.dashboard)}>
      <Paper className={classes.paper}>
        <Tabs centered value={activeTab} indicatorColor="primary">
          <Tab
            value="branches"
            label="Branches"
            component={Link}
            to="/dashboard/branches"
          />
          <Tab
            value="incoming"
            label="Incoming"
            component={Link}
            to="/dashboard/incoming"
          />
          <Tab
            value="outgoing"
            label="Outgoing"
            component={Link}
            to="/dashboard/outgoing"
          />
        </Tabs>
        <Switch>
          <Route path="/dashboard/incoming" component={Incoming} />
          <Route path="/dashboard/outgoing" component={Outgoing} />
          <Route path="/dashboard/branches" component={Branches} />
        </Switch>
      </Paper>
    </Container>
  )
}

export default Registry.add("Dashboard", Dashboard)
