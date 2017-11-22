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

import { fetchJSON } from "../utils/Fetch"
import { handleJSONResponse } from "../resources"
import { createdPendingRebase, cancelledPendingRebase } from "./review"
import { showErrorInModal } from "./ui"

export const prepareRebase = (reviewID, newUpstream) => async (dispatch) => {
  var body
  if (newUpstream !== undefined) {
    body = { new_upstream: newUpstream }
  } else {
    body = { history_rewrite: true }
  }
  const { updates } = dispatch(
    handleJSONResponse(
      await dispatch(
        fetchJSON({
          path: `reviews/${reviewID}/rebases`,
          include: ["commits", "users"],
          post: body,
        })
      )
    )
  )
  return updates.get("rebases").first()
}

export const cancelRebase = (rebase) => async (dispatch) => {
  dispatch(
    handleJSONResponse(
      await dispatch(
        fetchJSON({
          path: `rebases/${rebase.id}`,
          options: { method: "DELETE" },
        })
      )
    )
  )
}
