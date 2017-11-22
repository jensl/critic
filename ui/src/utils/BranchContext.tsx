/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
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

import React, { useContext, FunctionComponent } from "react"
import Branch from "../resources/branch"

const BranchContext = React.createContext<Branch | null>(null)

type Props = { branch: Branch }

export const SetBranch: FunctionComponent<Props> = ({ branch, children }) => (
  <BranchContext.Provider value={branch}>{children}</BranchContext.Provider>
)

export const useBranch = () => useContext(BranchContext)

export default SetBranch
