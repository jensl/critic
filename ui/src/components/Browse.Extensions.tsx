/*
 * Copyright 2020 the Critic contributors, Opera Software ASA
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
import Paper from "@material-ui/core/Paper"
import Toolbar from "@material-ui/core/Toolbar"
import Typography from "@material-ui/core/Typography"
import IconButton from "@material-ui/core/IconButton"
import MoreIcon from "@material-ui/icons/MoreVert"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import ExtensionList from "./Extension.List"
import { useSelector } from "../store"
import { useSubscription } from "../utils"
import { loadExtensions } from "../actions/extension"

const useStyles = makeStyles({
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
  },
})

const BrowseExtensions: FunctionComponent = () => {
  const classes = useStyles()
  const extensions = useSelector((state) => state.resource.extensions.byID)
  useSubscription(loadExtensions, [])
  console.log({ extensions })
  return (
    <Paper>
      <Toolbar className={classes.toolbar}>
        <Typography variant="h6">Extensions</Typography>
        <IconButton
          aria-label="display more actions"
          edge="end"
          color="inherit"
        >
          <MoreIcon />
        </IconButton>
      </Toolbar>
      <ExtensionList extensionIDs={extensions.keys()} />
    </Paper>
  )
}

export default Registry.add("Browse.Extensions", BrowseExtensions)
