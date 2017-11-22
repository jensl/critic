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
import clsx from "clsx"
import json2mq from "json2mq"

import AppBar from "@material-ui/core/AppBar"
import Toolbar from "@material-ui/core/Toolbar"
import Typography from "@material-ui/core/Typography"
import Button from "@material-ui/core/Button"
import IconButton from "@material-ui/core/IconButton"
import MenuIcon from "@material-ui/icons/Menu"
import { makeStyles, useTheme } from "@material-ui/core/styles"
import useMediaQuery from "@material-ui/core/useMediaQuery"
import useScrollTrigger from "@material-ui/core/useScrollTrigger"
import Slide from "@material-ui/core/Slide"

import Registry from "."
import { IsVisible as SidebarIsVisible } from "./Application.Sidebar"
import { kDialogID as SignInDialogID } from "./Dialog.SignIn"
import UserName from "./User.Name"
import constants from "../constants"
import { useUserSetting, useSignedInUser, useDialog } from "../utils"

const useStyles = makeStyles((theme) => ({
  applicationTopBar: {
    flexGrow: 0,
    color: "default",
  },
  grow: {
    flexGrow: 1,
  },
  menuButton: {
    marginLeft: -12,
    marginRight: 20,
  },
  unshift: {
    transition: theme.transitions.create(["margin", "width"], {
      easing: theme.transitions.easing.sharp,
      duration: theme.transitions.duration.leavingScreen,
    }),
  },
  shift: {
    width: `calc(100% - ${constants.sidebarWidth}px)`,
    marginLeft: constants.sidebarWidth,
    transition: theme.transitions.create(["margin", "width"], {
      easing: theme.transitions.easing.easeOut,
      duration: theme.transitions.duration.enteringScreen,
    }),
  },
  hide: { display: "none" },
}))

type HideOnScrollProps = {
  children: React.ReactElement
}

const HideOnScroll = ({ children }: HideOnScrollProps) => {
  const trigger = useScrollTrigger()

  const query = json2mq({ minHeight: 1024 })
  if (useMediaQuery(query)) return <>{children}</>

  return (
    <Slide appear={false} direction="down" in={!trigger}>
      {children}
    </Slide>
  )
}

const TopBar: FunctionComponent = () => {
  const classes = useStyles()
  const theme = useTheme()
  const usePersistent = useMediaQuery(theme.breakpoints.up("lg"))
  const signedInUser = useSignedInUser()
  const [sidebarVisible, setSidebarVisible] = useUserSetting(SidebarIsVisible)
  const { openDialog: openSignIn } = useDialog(SignInDialogID)
  const session = []
  if (signedInUser)
    session.push(
      <Typography key="user-name" variant="h6" color="inherit">
        <UserName userID={signedInUser.id} />
      </Typography>
    )
  else
    session.push(
      <Button key="sign-in" color="inherit" onClick={openSignIn}>
        Sign in
      </Button>
    )
  return (
    <HideOnScroll>
      <AppBar
        position="fixed"
        className={clsx(classes.applicationTopBar, {
          [classes.unshift]: usePersistent && !sidebarVisible,
          [classes.shift]: usePersistent && sidebarVisible,
        })}
      >
        <Toolbar>
          {sidebarVisible ? null : (
            <IconButton
              className={clsx(classes.menuButton, {
                [classes.hide]: sidebarVisible,
              })}
              color="inherit"
              aria-label="Menu"
              onClick={() => setSidebarVisible(true)}
            >
              <MenuIcon />
            </IconButton>
          )}
          <Typography variant="h6" color="inherit" className={classes.grow}>
            Critic
          </Typography>
          {session}
        </Toolbar>
      </AppBar>
    </HideOnScroll>
  )
}

export default Registry.add("Application.TopBar", TopBar)
