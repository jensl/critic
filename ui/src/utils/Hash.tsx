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

import React, { useContext, useMemo } from "react"

import { maybeParseInt } from "./Strings"
import { useLocation, useHistory } from "react-router"
import { filtered, sorted, map, chain } from "./Functions"

type HashKey = string
type HashValue = number | string | boolean
type HashEntry = [HashKey, HashValue]

type ParsedHash = Map<HashKey, HashValue>
type HashUpdates = { [key: string]: HashValue | null }
type History = ReturnType<typeof useHistory>

export const parseHash = (hash: string) => {
  const result = new Map()
  for (const component of hash.substring(1).split("/")) {
    if (!component.trim() || component.startsWith(":")) continue
    const match = /([^:]+)(?::(.*))?/.exec(component)
    if (match) {
      const [, name, value = true] = match
      result.set(name, typeof value === "string" ? maybeParseInt(value) : value)
    }
  }
  return result
}

export const updateHash = (
  hash: ParsedHash,
  history: History,
  updates: HashUpdates,
) => {
  console.log({ hash, updates })
  const newHash = sorted(
    map(
      filtered(
        chain(
          map(hash.entries(), ([key, value]): [HashKey, HashValue | null] => [
            key,
            updates.hasOwnProperty(key) ? updates[key] : value,
          ]),
          filtered(Object.entries(updates), ([key]) => !hash.has(key)),
        ),
        ([_, value]) => value !== null,
      ),
      ([key, value]) => (value === true ? key : `${key}:${value}`),
    ),
  ).join("/")

  console.log({ newHash })

  history.replace(history.location.pathname + (newHash ? "#" + newHash : ""))
}

export type UpdateHash = (updates: HashUpdates) => void

class HashContextValue {
  constructor(
    readonly location: ReturnType<typeof useLocation> | null,
    readonly history: ReturnType<typeof useHistory> | null,
    readonly hash: ParsedHash,
    readonly updateHash: UpdateHash,
  ) {}

  static default() {
    return new HashContextValue(null, null, new Map(), () => null)
  }
}

const HashContext = React.createContext(HashContextValue.default())

export const ProvideHashContext: React.FunctionComponent = ({ children }) => {
  const location = useLocation()
  const history = useHistory()

  const hash = useMemo(() => parseHash(location.hash), [location])
  const value = useMemo(
    () =>
      new HashContextValue(
        location,
        history,
        hash,
        updateHash.bind(null, hash, history),
      ),
    [location, history, hash],
  )

  return <HashContext.Provider value={value}>{children}</HashContext.Provider>
}

export const useHash = () => {
  const value = useContext(HashContext)
  return { hash: value.hash, updateHash: value.updateHash }
}

const hash = { parse: parseHash, update: updateHash }

export default hash
