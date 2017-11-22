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

import { joinPaths } from "./Strings"

export const showFilePath = ({ repository, commit, path }) =>
  joinPaths(`/repository/${repository.name}/file/${commit.sha1}`, path)

export const showTreePath = ({ repository, commit, path = null }) => {
  const base = `/repository/${repository.name}/tree/${commit.sha1}`
  if (path === null) return base
  return joinPaths(base, path)
}
