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
import { makeStyles } from "@material-ui/core/styles"

import { documentClicked } from "../actions/ui"

import Registry from "."
import TopBar from "./Application.TopBar"
import Sidebar from "./Application.Sidebar"
import Content from "./Application.Content"
import { useSelector, useDispatch } from "../store"

const useStyles = makeStyles({
  application: {
    display: "flex",
    height: "100%",
  },
})

const ApplicationStructure: FunctionComponent = () => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const started = useSelector((state) => state.ui.rest.started)
  if (!started) return null
  return (
    <div
      className={classes.application}
      onMouseDown={(ev) => {
        let target: Node | null = ev.target as Node
        while (target) {
          if (target.nodeType === Node.ELEMENT_NODE) {
            if ((target as HTMLElement).classList.contains("MuiDialog-root"))
              return
          }
          target = target.parentNode
        }
        dispatch(documentClicked())
      }}
    >
      <TopBar />
      <Sidebar />
      <Content />
    </div>
  )
}

export default Registry.add("Application.Structure", ApplicationStructure)
