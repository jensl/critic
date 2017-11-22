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

import { State } from "../state"
import { useSelector, useDispatch } from "../store"
import { Action } from "../actions"
import { useCallback } from "react"

class Value<T> {
  constructor(readonly key: string, readonly defaultValue: T) {}

  read(state: State): T {
    return state.ui.values.get(this.key) ?? this.defaultValue
  }

  set(value: T): Action {
    return { type: "SET_VALUE", key: this.key, value }
  }

  delete(): Action {
    return { type: "DELETE_VALUE", key: this.key }
  }
}

export const useValue = <T>(value: Value<T>): [T, (newValue: T) => void] => {
  const dispatch = useDispatch()
  return [
    useSelector((state) => value.read(state)),
    useCallback((newValue: T) => void dispatch(value.set(newValue)), [
      value,
      dispatch,
    ]),
  ]
}

export const useValueWithFallback = <T, U>(
  value: Value<T> | null,
  fallback: U
): T | U => {
  return useSelector((state) => (value ? value.read(state) : fallback))
}

export default Value
