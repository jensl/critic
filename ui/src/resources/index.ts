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

import {
  ResourceError,
  fetch,
  fetchOne,
  createResources,
  createResource,
  updateResources,
  updateResource,
  deleteResource,
} from "./fetch"
import {
  withArgument,
  withArguments,
  withParameters,
  withContext,
  include,
  includeFields,
  excludeFields,
  expectStatuses,
  handleError,
} from "./requestoptions"
import { RequestOptions as _RequestOptions } from "./types"
import definitions from "./definitions"

export type RequestOptions = _RequestOptions

export {
  ResourceError,
  fetch,
  fetchOne,
  createResources,
  createResource,
  updateResources,
  updateResource,
  deleteResource,
  withArgument,
  withArguments,
  withParameters,
  withContext,
  include,
  includeFields,
  excludeFields,
  expectStatuses,
  handleError,
}

const resource = {
  fetch,
  fetchOne,
  create: createResource,
  update: updateResource,
  delete: deleteResource,
  definitions,
}

export default resource
