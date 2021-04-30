/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import React, { FunctionComponent } from "react"
import { Redirect, Route, Switch } from "react-router"
import clsx from "clsx"

import { makeStyles, useTheme } from "@material-ui/core/styles"
import useMediaQuery from "@material-ui/core/useMediaQuery"

import constants from "../constants"
import { IsVisible as SidebarIsVisible } from "./Application.Sidebar"
import Breadcrumbs from "./Application.Breadcrumbs"
import NotFound from "./Application.NotFound"
import Suggestions from "./Suggestions"
import AccountSettings from "./Settings.Account"
import SystemSettings from "./Settings.System"
import ReviewContext from "./Review.Context"
import Dashboard from "./Dashboard"
import DashboardReview from "./Dashboard.Review"
import SelectionHighlight from "./Selection.Highlight"
import SelectionRectangle from "./Selection.Rectangle"
import Help from "./Help"
import Tutorial from "./Tutorial"
import RepositoryRouter from "./Repository.Router"
import BrowseRepositories from "./Browse.Repositories"
import BrowseExtensions from "./Browse.Extensions"
import Extension from "./Extension"
import { useSignedInUser, useUserSetting } from "../utils"

const useStyles = makeStyles((theme) => ({
  applicationContent: {
    display: "flex",
    flexDirection: "column",
    flexGrow: 1,
    paddingLeft: theme.spacing(3),
    paddingRight: theme.spacing(3),

    [theme.breakpoints.down("xs")]: {
      paddingLeft: theme.spacing(1),
      paddingRight: theme.spacing(1),
    },
  },
  unshift: {
    transition: theme.transitions.create("margin", {
      easing: theme.transitions.easing.sharp,
      duration: theme.transitions.duration.leavingScreen,
    }),
    marginLeft: -constants.sidebarWidth,
  },
  shift: {
    transition: theme.transitions.create("margin", {
      easing: theme.transitions.easing.easeOut,
      duration: theme.transitions.duration.enteringScreen,
    }),
    marginLeft: 0,
  },

  main: {
    paddingTop: theme.spacing(3),
    paddingBottom: theme.spacing(3),
    display: "flex",
    flexDirection: "column",
    flexGrow: 1,
  },

  sidebarHeader: {
    display: "flex",
    alignItems: "center",
    padding: "0 8px",
    ...theme.mixins.toolbar,
    justifyContent: "flex-end",
  },
}))

const RedirectToDefaultView = () => {
  const signedInUser = useSignedInUser()
  return signedInUser ? <Redirect to="/suggestions" /> : null
}

const Content: FunctionComponent = () => {
  const classes = useStyles()
  const theme = useTheme()
  const usePersistent = useMediaQuery(theme.breakpoints.up("lg"))
  const [sidebarVisible] = useUserSetting(SidebarIsVisible)
  return (
    <div
      className={clsx(classes.applicationContent, {
        [classes.unshift]: usePersistent && !sidebarVisible,
        [classes.shift]: usePersistent && sidebarVisible,
      })}
    >
      <main className={classes.main}>
        <div className={classes.sidebarHeader} />
        <Breadcrumbs />
        <Switch>
          <Route exact path="/" component={RedirectToDefaultView} />
          <Route
            path="/review/:reviewID/:activeTab?"
            component={ReviewContext}
          />
          <Route path="/repository/:name" component={RepositoryRouter} />
          <Route
            path="/dashboard/:category/review/:reviewID/:activeTab?"
            component={DashboardReview}
          />
          <Route path="/dashboard/:activeTab" component={Dashboard} />
          <Route
            path="/settings/account/:section?"
            component={AccountSettings}
          />
          <Route path="/settings/system/:section?" component={SystemSettings} />
          <Route path="/suggestions" component={Suggestions} />
          <Route path="/help" component={Help} />
          <Route path="/tutorial/:tutorialID" component={Tutorial} />
          <Route path="/browse/repositories" component={BrowseRepositories} />
          <Route path="/browse/extensions" component={BrowseExtensions} />
          <Route path="/extension/:key/:activeTab?" component={Extension} />
          <Route component={NotFound} />
        </Switch>
        <SelectionHighlight />
        <SelectionRectangle />
      </main>
    </div>
  )
}

export default Content