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

import React, { FunctionComponent, useContext } from "react"
import { assertNotNull } from "../debug"

import Changeset from "../resources/changeset"
import MergeAnalysis from "../resources/mergeanalysis"

type Props = {
  changeset: Changeset
  expandedFileIDs: ReadonlySet<number | string>
  mergeAnalysis?: MergeAnalysis | null
  conflictResolutions?: Changeset | null
}

const ChangesetContext = React.createContext<Partial<Props>>({})

export const SetChangeset: FunctionComponent<Props> = ({
  children,
  ...props
}) => (
  <ChangesetContext.Provider value={props}>
    {children}
  </ChangesetContext.Provider>
)

export const useChangeset = () => {
  const { changeset, expandedFileIDs, ...rest } = useContext(ChangesetContext)
  assertNotNull(changeset)
  assertNotNull(expandedFileIDs)
  return { changeset, expandedFileIDs, ...rest }
}
