/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
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

import produce from "./immer"
import { Reducer } from "redux"

import { DATA_UPDATE, Action } from "../actions"

interface ResourceWithID<ID> {
  id: ID
}

function defaultGetID<ID, T extends ResourceWithID<ID>>(resource: T): ID {
  return resource.id
}

//type Reducer<State> = (state: State, action: Action) => State

/* Reducer for the primary mapping of resoucre ID to resource object. */
export const primaryMap = <T, ID extends number | string>(
  resourceName: string,
  getID: (resource: T) => ID | null = defaultGetID as (resource: T) => ID
) =>
  produce<Map<ID, T>>((draft: Map<ID, T>, action: Action) => {
    if (action.type === DATA_UPDATE) {
      const updates = action.updates.get(resourceName) as T[]
      if (updates)
        for (const item of updates) {
          const id = getID(item)
          if (id !== null) draft.set(id, item)
        }
      const deleted = action.deleted?.get(resourceName) as Set<ID> | undefined
      if (deleted) for (const id of deleted) draft.delete(id)
    }
  }, new Map())

const lookupDelete = <Key, ID>(draft: Map<Key, ID>, deleted?: Set<ID>) => {
  if (deleted) {
    const deleteKeys = [...draft.entries()]
      .filter(([key, id]) => deleted.has(id))
      .map(([key]) => key)
    for (const key of deleteKeys) draft.delete(key)
  }
}

/* Reducer for lookup mappings of secondary key to resource ID. */
export const lookupMap = <T, Key, ID extends number | string>(
  resourceName: string,
  getKey: (resource: T) => null | Key,
  getID: (resource: T) => ID = defaultGetID as (resource: T) => ID
) =>
  produce<Map<Key, ID>>((draft: Map<Key, ID>, action: Action) => {
    if (action.type === DATA_UPDATE) {
      const updates = action.updates.get(resourceName) as T[]
      if (updates)
        for (const item of updates) {
          const key = getKey(item)
          if (key !== null) draft.set(key, getID(item))
        }
      lookupDelete(
        draft,
        action.deleted?.get(resourceName) as Set<ID> | undefined
      )
    }
  }, new Map())

/* Reducer for lookup mappings of multiple secondary keys to resource ID. */
export const lookupManyMap = <T, Key, ID extends number | string>(
  resourceName: string,
  getKeys: (resource: T) => Key[],
  getID: (resource: T) => ID = defaultGetID as (resource: T) => ID
) =>
  produce<Map<Key, ID>>((draft: Map<Key, ID>, action: Action) => {
    if (action.type === DATA_UPDATE) {
      const updates = action.updates.get(resourceName) as T[]
      if (updates)
        for (const item of updates) {
          const id = getID(item)
          for (const key of getKeys(item)) draft.set(key, id)
        }
      lookupDelete(
        draft,
        action.deleted?.get(resourceName) as Set<ID> | undefined
      )
    }
  }, new Map())

/* Reducer for mappings of resource ID (or other key) to auxilliary data. */
export const auxilliaryMap = <T, ID, Auxilliary>(
  resourceName: string,
  mapper: (resource: T) => [ID, Auxilliary | null]
) =>
  produce<Map<ID, Auxilliary>>((draft: Map<ID, Auxilliary>, action: Action) => {
    if (action.type === DATA_UPDATE) {
      const updates = action.updates.get(resourceName)
      if (updates)
        for (const item of updates) {
          const [id, auxilliary] = mapper(item)
          if (auxilliary) draft.set(id, auxilliary)
        }
      const deleted = action.deleted?.get(resourceName) as Set<ID> | undefined
      if (deleted) for (const id of deleted) draft.delete(id)
    }
  }, new Map())
