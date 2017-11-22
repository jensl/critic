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

/*
import { connect } from "react-redux"
import { compose } from "redux"

import { loadFileByID, loadFileByPath } from "../actions/file"
import { withSubscriptions } from "./ResourceSubscriber"

// Use |path| or |fileID| input props and adds |file|.
export const resolveFile = compose(
  connect((state, { fileID = null, path = null }) => {
    const file = state.resource.files.byID.get(
      fileID !== null ? fileID : state.resource.files.byPath.get(path, null),
      null
    )
    return { file }
  }),
  withSubscriptions(({ fileID = null, path = null }) => [
    fileID !== null
      ? {
          action: loadFileByID,
          parameters: { fileID },
        }
      : {
          action: loadFileByPath,
          parameters: { path },
        },
  ])
)
*/
