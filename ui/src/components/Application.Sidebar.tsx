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

import ChevronLeftIcon from "@material-ui/icons/ChevronLeft"
import IconButton from "@material-ui/core/IconButton"
import Drawer from "@material-ui/core/Drawer"
import Divider from "@material-ui/core/Divider"
import List from "@material-ui/core/List"
import ListSubheader from "@material-ui/core/ListSubheader"
import ListItem from "@material-ui/core/ListItem"
import ListItemText from "@material-ui/core/ListItemText"
import { makeStyles, useTheme } from "@material-ui/core/styles"
import useMediaQuery from "@material-ui/core/useMediaQuery"

import Registry from "."
import Link from "./Application.Sidebar.Link"
import constants from "../constants"
import userSettings from "../userSettings"
import { loadReviewCategory } from "../actions/review"
import { logout } from "../actions/session"
import { useSubscription, SidebarContext, useUserSetting } from "../utils"
import { useSessionID } from "../utils/SessionContext"
import { useDispatch, useSelector } from "../store"

const useStyles = makeStyles((theme) => ({
  applicationSidebar: {
    width: constants.sidebarWidth,
    flexShrink: 0,
    display: "flex",
    flexFlow: "column",
    justifyContent: "space-between",
  },
  paper: {
    width: constants.sidebarWidth,
  },
  header: {
    display: "flex",
    flexDirection: "row",
    alignItems: "center",
    padding: "0 8px",
    ...theme.mixins.toolbar,
  },
  bottom: {
    flexGrow: 1,
    display: "flex",
    flexDirection: "column",
    justifyContent: "flex-end",
  },
}))

export const IsVisible = userSettings.sidebar.isVisible

export const Sidebar: FunctionComponent = () => {
  const classes = useStyles()
  const theme = useTheme()
  const usePersistent = useMediaQuery(theme.breakpoints.up("lg"))
  const dispatch = useDispatch()
  const [isVisible, setIsVisible] = useUserSetting(IsVisible)
  const sessionID = useSessionID()
  const reviewCategories = useSelector(
    (state) => state.ui.rest.reviewCategories
  )
  useSubscription(loadReviewCategory, "incoming", sessionID)
  useSubscription(loadReviewCategory, "outgoing", sessionID)
  const incoming = reviewCategories.get("incoming", { size: null }).size
  const outgoing = reviewCategories.get("outgoing", { size: null }).size
  const hide = () => setIsVisible(false)
  const hideIfTemporary = () => void (usePersistent || hide())
  const variant = usePersistent ? "persistent" : "temporary"
  return (
    <Drawer
      className={classes.applicationSidebar}
      variant={variant}
      anchor="left"
      open={isVisible}
      onClose={hide}
      classes={{ paper: classes.paper }}
    >
      <SidebarContext.Provider value={{ variant, hideIfTemporary }}>
        <div className={classes.header}>
          <IconButton onClick={hide}>
            <ChevronLeftIcon />
          </IconButton>
        </div>
        <Divider />
        <div className="top">
          <List dense>
            <Link href="/suggestions" text="Suggestions" />
          </List>
          <List dense subheader={<ListSubheader>Dashboard</ListSubheader>}>
            <Link
              href="/dashboard/branches"
              badge={{ badgeContent: 1, color: "primary" }}
              text="My branches"
            />
            <Link
              href="/dashboard/incoming"
              badge={{ badgeContent: incoming, color: "primary" }}
              text="Incoming reviews"
            />
            <Link
              href="/dashboard/outgoing"
              badge={{ badgeContent: outgoing, color: "primary" }}
              text="Outgoing reviews"
            />
          </List>
          <List dense subheader={<ListSubheader>Browse</ListSubheader>}>
            <Link href="/browse/repositories" text="Repositories" />
            <Link href="/browse/reviews" text="Reviews" />
            <Link href="/browse/extensions" text="Extensions" />
          </List>
        </div>
        <div className={classes.bottom}>
          <List dense subheader={<ListSubheader>Settings</ListSubheader>}>
            <Link href="/settings/account" text="Account" />
          </List>
          <Divider />
          <List dense>
            <ListItem button onClick={() => dispatch(logout())}>
              <ListItemText primary="Sign out" />
            </ListItem>
          </List>
        </div>
      </SidebarContext.Provider>
    </Drawer>
  )
}

export default Registry.add("Application.SideBar", Sidebar)
