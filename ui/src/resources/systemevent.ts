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

import { primaryMap } from "../reducers/resource"

type SystemEventData = {
  id: number
  category: string
  key: string
  title: string
  data: any
  handled: boolean
}

type SystemEventProps = SystemEventData

class SystemEvent {
  constructor(
    readonly id: number,
    readonly category: string,
    readonly key: string,
    readonly title: string,
    readonly data: any,
    readonly handled: boolean
  ) {}

  static new(props: SystemEventProps) {
    return new SystemEvent(
      props.id,
      props.category,
      props.key,
      props.title,
      props.data,
      props.handled
    )
  }

  static reducer = primaryMap<SystemEvent, number>("systemevents")

  get props(): SystemEventProps {
    return this
  }
}

export default SystemEvent
