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

import { countWithUnit } from "./Strings"

const timeSince = (timestamp) => {
  if (timestamp instanceof Date) timestamp = timestamp.valueOf()
  else timestamp = timestamp * 1000

  const seconds = Math.floor((Date.now() - timestamp) / 1000)
  var interval = Math.floor(seconds / 31536000)

  const withUnit = (unit) => countWithUnit(Math.floor(interval), unit)

  if (interval !== 0) return withUnit("year")
  interval = Math.floor(seconds / 2592000)
  if (interval !== 0) return withUnit("month")
  interval = Math.floor(seconds / 86400)
  if (interval !== 0) return withUnit("day")
  interval = Math.floor(seconds / 3600)
  if (interval !== 0) return withUnit("hour")
  interval = Math.floor(seconds / 60)
  if (interval !== 0) return withUnit("minute")
  return withUnit("second")
}

export default timeSince
