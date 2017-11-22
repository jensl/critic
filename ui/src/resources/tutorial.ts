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

import { primaryMap } from "../reducers/resource"

type TutorialData = {
  id: string
  source: string
}

type TutorialProps = TutorialData

class Tutorial {
  constructor(readonly id: string, readonly source: string) {}

  static new(props: TutorialProps) {
    return new Tutorial(props.id, props.source)
  }

  static reducer = primaryMap<Tutorial, string>("tutorials")

  get props(): TutorialProps {
    return this
  }
}

export default Tutorial
