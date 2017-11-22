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

import React from "react"

import Registry from "."
import AddReply from "./Discussion.Action.AddReply"
import RaiseIssue from "./Discussion.Action.RaiseIssue"
import WriteNote from "./Discussion.Action.WriteNote"
import Edit from "./Discussion.Action.Edit"
import Delete from "./Discussion.Action.Delete"
import Save from "./Discussion.Action.Save"
import Discard from "./Discussion.Action.Discard"

const Actions: React.FunctionComponent = () => (
  <>
    <AddReply />
    <RaiseIssue />
    <WriteNote />
    <Edit />
    <Delete />
    <Save />
    <Discard />
  </>
)

export default Registry.add("Discussion.Actions", Actions)
