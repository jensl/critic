import React from "react"
import { Redirect, Route, Switch, useParams } from "react-router"
import { Link } from "react-router-dom"
import clsx from "clsx"
import loadable from "@loadable/component"

import Container from "@material-ui/core/Container"
import Paper from "@material-ui/core/Paper"
import Tab from "@material-ui/core/Tab"
import Tabs from "@material-ui/core/Tabs"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Breadcrumb from "./Breadcrumb"
//import ExtensionCalls from "./Extension.Calls"
import ExtensionDescription from "./Extension.Description"
import ExtensionHeader from "./Extension.Header"
import { loadExtensionByKey } from "../actions/extension"
import { useResource, useSubscription } from "../utils"
import { WithExtension } from "../utils/ExtensionContext"
import { useDeducedVersion } from "../utils/Extension"

const ExtensionCalls = loadable(() => import("./Extension.Calls"))

const useStyles = makeStyles((theme) => ({
  container: {
    [theme.breakpoints.down("sm")]: {
      paddingLeft: theme.spacing(1),
      paddingRight: theme.spacing(1),
    },
    display: "flex",
    flexDirection: "column",
    flexGrow: 1,
  },

  paper: {
    padding: theme.spacing(2, 0),
    display: "flex",
    flexDirection: "column",
    flexGrow: 1,
  },
}))

type Params = {
  key: string
  activeTab: string | undefined
}

const Extension: React.FunctionComponent = () => {
  const classes = useStyles()
  const { key, activeTab } = useParams<Params>()

  useSubscription(loadExtensionByKey, [key])

  const extension = useResource("extensions", ({ byID, byKey }) =>
    byID.get(byKey.get(key) ?? -1),
  )
  const installation = useResource("extensioninstallations", (byID) =>
    byID.get(extension?.installation ?? -1),
  )
  const version = useDeducedVersion(extension)

  if (!extension) return null

  const prefix = `/extension/${extension.key}`
  if (!activeTab) return <Redirect to={`${prefix}/description`} />

  console.log({ extension, installation, version })

  return (
    <WithExtension
      extension={extension}
      installation={installation}
      version={version}
    >
      <Breadcrumb label="extensions" path="/browse/extensions">
        <Breadcrumb category="extension" label={extension.key} path={prefix}>
          <Container className={clsx(classes.container)} maxWidth="lg">
            <ExtensionHeader />
            <Paper className={classes.paper}>
              <Tabs centered value={activeTab} indicatorColor="primary">
                <Tab
                  component={Link}
                  to={`${prefix}/description`}
                  value="description"
                  label="Description"
                />
                <Tab
                  component={Link}
                  to={`${prefix}/calls`}
                  value="calls"
                  label="Calls"
                />
              </Tabs>
              <Switch>
                <Route
                  path={`${prefix}/description`}
                  component={ExtensionDescription}
                />
                <Route path={`${prefix}/calls`} component={ExtensionCalls} />
              </Switch>
            </Paper>
          </Container>
        </Breadcrumb>
      </Breadcrumb>
    </WithExtension>
  )
}

export default Registry.add("Extension", Extension)
