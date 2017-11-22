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

import { setFlag, clearFlag, toggleFlag } from "../actions/ui"
import { State } from "../state"
import { useSelector, useDispatch } from "../store"

class Flag {
  constructor(readonly key: string) {}

  read(state: State) {
    return state.ui.flags.has(this.key)
  }

  get set() {
    return setFlag(this.key)
  }

  get clear() {
    return clearFlag(this.key)
  }

  get toggle() {
    return toggleFlag(this.key)
  }
}

export const useFlag = (flag: Flag | null): [boolean, () => void] => {
  const dispatch = useDispatch()
  return [
    useSelector((state) => (flag ? flag.read(state) : false)),
    flag ? () => dispatch(flag.toggle) : () => null,
  ]
}

export default Flag
