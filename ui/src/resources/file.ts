/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the
); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an
 BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import { combineReducers } from "redux"
import { primaryMap, lookupMap } from "../reducers/resource"
import { FileID } from "./types"

type FileData = {
  id: FileID
  path: string
}

type FileProps = FileData

class File {
  constructor(readonly id: FileID, readonly path: string) {}

  static new(props: FileProps) {
    return new File(props.id, props.path)
  }

  static reducer = combineReducers({
    byID: primaryMap<File, number>("files"),
    byPath: lookupMap<File, string, number>("files", (file) => file.path),
  })

  get props(): FileProps {
    return this
  }
}

export default File
