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

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Token from "../utils/Token"
import { useSelector } from "../store"

const useStyles = makeStyles((theme) => ({
  connectedInput: {},
}))

type Props = {
  className?: string
  inputID: Token
}

const ConnectedInput: FunctionComponent<Props> = ({ className, inputID }) => {
  const classes = useStyles()
  const connectedInputs = useSelector((state) => state.ui.connectedInputs)
  const connectedInput = connectedInputs.get(inputID, null)
  if (!connectedInput) return null
  return (
    <div className={clsx(className, classes.connectedInput)}>
      <textarea defaultValue={connectedInput.resourceValue || ""} />
    </div>
  )
}

export default Registry.add("ConnectedInput", ConnectedInput)
