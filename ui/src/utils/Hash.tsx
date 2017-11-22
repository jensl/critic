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

import React, { useContext } from "react"
import Immutable from "immutable"

import { maybeParseInt } from "./Strings"
import { useLocation, useHistory } from "react-router"

type ParsedHash = Immutable.OrderedMap<string, number | string | boolean>
type HashUpdates = { [key: string]: string | null }
type History = ReturnType<typeof useHistory>

export const parseHash = (hash: string) => {
  return (Immutable.OrderedMap() as ParsedHash).withMutations((result) => {
    for (const component of hash.substring(1).split("/")) {
      if (!component.trim() || component.startsWith(":")) continue
      const match = /([^:]+)(?::(.*))?/.exec(component)
      if (match) {
        const [, name, value = true] = match
        result.set(
          name,
          typeof value === "string" ? maybeParseInt(value) : value
        )
      }
    }
  })
}

export const updateHash = (
  hash: ParsedHash,
  history: History,
  updates: HashUpdates
) => {
  const components = hash
    .toKeyedSeq()
    .filterNot((_, key) => updates.hasOwnProperty(key) && updates[key] === null)
    .map((value, key) => (updates.hasOwnProperty(key) ? updates[key] : value))
    .toOrderedMap()
    .withMutations((components) => {
      for (const key of Object.keys(updates)) {
        if (hash.has(key)) continue
        const value = updates[key]
        if (value === null) continue
        components.set(key, value)
      }
    })

  const newHash = components
    .toKeyedSeq()
    .map((value, key) => (value === true ? key : `${key}:${value}`))
    .join("/")

  history.replace(history.location.pathname + (newHash ? "#" + newHash : ""))
}

type Props = {
  location: ReturnType<typeof useLocation> | null
  history: ReturnType<typeof useHistory> | null
  hash: ParsedHash
  updateHash: (updates: HashUpdates) => void
}

class HashContextValue extends Immutable.Record<Props>(
  {
    location: null,
    history: null,
    hash: Immutable.Map(),
    updateHash: () => null,
  },
  "HashContextValue"
) {}

const HashContext = React.createContext(new HashContextValue())

export const ProvideHashContext: React.FunctionComponent = ({ children }) => {
  const currentValue = new HashContextValue()
  const location = useLocation()
  const history = useHistory()

  const makeHashContextValue = () => {
    if (currentValue.location === location) return currentValue
    const hash = parseHash(location.hash)
    console.log({ hash, location })
    return new HashContextValue({
      location,
      history,
      hash,
      updateHash: updateHash.bind(null, hash, history),
    })
  }

  return (
    <HashContext.Provider value={makeHashContextValue()}>
      {children}
    </HashContext.Provider>
  )
}

export const useHash = () => {
  const value = useContext(HashContext)
  console.log({ value })
  return { hash: value.hash, updateHash: value.updateHash }
}

export default { parse: parseHash, update: updateHash }
