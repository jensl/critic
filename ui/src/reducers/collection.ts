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

import Immutable from "immutable"

import { InvalidItem, DATA_UPDATE } from "../actions"

const generateUpdates = (
  items: Immutable.List<any>,
  callback: (item: any) => { key: any; value: any; isImmutable?: boolean }[],
  state: Immutable.Map<any, any>
) =>
  state.withMutations((map) =>
    items.forEach((item) => {
      for (const { key, value, isImmutable = false } of callback(item))
        try {
          if (
            isImmutable
              ? !state.has(key)
              : typeof value === "number"
              ? value !== state.get(key)
              : !value.equals(state.get(key))
          )
            map.set(key, value)
        } catch (_) {
          console.error("no equals", value)
        }
    })
  )

type TableCallback = (item: any) => { key: any; value: any }[]

interface ItemWithID<IDType> {
  id: IDType
}

export function byID<IDType, Item extends ItemWithID<IDType>>(
  item: Item
): { key: IDType; value: Item }[] {
  return [{ key: item.id, value: item }]
}

export const byIDImmutable: TableCallback = (item: any) => [
  { key: item.id, value: item, isImmutable: true },
]
export const lookup = (prop: string) => (item: any) => [
  { key: item[prop], value: item.id },
]
export const lookupImmutable = (prop: string) => (item: any) => [
  { key: item[prop], value: item.id, isImmutable: true },
]

type SimpleTable = TableCallback
type ComplexTable = { [name: string]: TableCallback }

type ReducerFunc = (state: undefined | any, action: any) => any
type LookupByIDFunc = (state: any, id: any) => any

type CreateCollectionOptions = {
  reducer?: null | ReducerFunc
  lookupByID?: null | LookupByIDFunc
}

export type Collection = any

interface TypedAction {
  type: string
}

interface DataUpdateAction extends TypedAction {
  updates: Immutable.Map<string, Immutable.List<any>>
  deleted: Immutable.Map<string, Immutable.Set<any>>
  invalid: Immutable.Map<string, Immutable.Set<any>>
}

export function createSimpleCollection<ItemID, Item>(resourceName: string) {
  type State = Immutable.Map<ItemID, Item | InvalidItem>
  function handleDataUpdate(state: State, action: DataUpdateAction) {
    const stateBefore = state
    const items = action.updates.get(resourceName)
    const invalidIDs = action.invalid
      ? action.invalid.get(resourceName, null)
      : null
    const deletedIDs = action.deleted
      ? action.deleted.get(resourceName, null)
      : invalidIDs
    if (!items && !deletedIDs && !invalidIDs) {
      return state
    }
    if (items) {
      state = generateUpdates(items, byID, state)
      if (state !== stateBefore)
        if (state.equals(stateBefore))
          console.error(`${resourceName} UPDATED BUT EQUAL!`)
        else console.info(`${resourceName} updated`)
    }
    if (deletedIDs)
      state = state.withMutations((state: State) => {
        deletedIDs.forEach((itemID) => state.delete(itemID))
      })
    if (invalidIDs) {
      state = state.withMutations((state: State) => {
        invalidIDs.forEach((itemID) =>
          state.set(itemID, new InvalidItem(itemID))
        )
      })
    }
    return state
  }
  return function reducer<Action extends TypedAction>(
    state: State = Immutable.Map<ItemID, Item | InvalidItem>(),
    action: Action
  ) {
    switch (action.type) {
      case DATA_UPDATE:
        return handleDataUpdate(state, (action as unknown) as DataUpdateAction)

      default:
        return state
    }
  }
}

export function createCollection<ItemID, Item>(
  resourceName: string,
  table: SimpleTable | ComplexTable = byID,
  { reducer = null, lookupByID = null }: CreateCollectionOptions = {}
) {
  var defaultState: any
  const simple = typeof table === "function"
  var recordType = null
  if (simple) {
    defaultState = Immutable.Map<ItemID, Item>()
  } else {
    const fields: {
      [name: string]: Immutable.Map<any, ItemID | Item>
    } = {}
    for (const tableName of Object.keys(table)) {
      fields[tableName] = Immutable.Map()
    }
    if (reducer) {
      Object.assign(fields, reducer(undefined, {}))
    }
    recordType = Immutable.Record(fields, `Collections(${resourceName})`)
    defaultState = new recordType()
  }
  if (lookupByID === null) {
    if (table === byID) lookupByID = (state, id) => state.get(id)
    else {
      const complexTable = table as ComplexTable
      for (const tableName of Object.keys(complexTable))
        if (complexTable[tableName] === byID)
          lookupByID = (state, id) => state[tableName].get(id)
    }
  }
  const mainReducer = (state: any = defaultState, action: any) => {
    switch (action.type) {
      case DATA_UPDATE:
        const stateBefore = state
        const items = action.updates.get(resourceName)
        const invalidIDs = action.invalid
          ? action.invalid.get(resourceName, null)
          : null
        const deletedIDs = action.deleted
          ? action.deleted.get(resourceName, null)
          : invalidIDs
        if (!items && !deletedIDs && !invalidIDs) {
          return state
        }
        var newState = state
        if (items) {
          if (simple) {
            const updates = generateUpdates(
              items,
              table as SimpleTable,
              newState
            )
            newState = newState.merge(updates)
          } else {
            for (const tableName of Object.keys(table)) {
              const updates = generateUpdates(
                items,
                (table as ComplexTable)[tableName],
                newState.get(tableName)
              )
              newState = newState.set(
                tableName,
                newState.get(tableName).merge(updates)
              )
            }
          }
          if (newState !== stateBefore)
            if (newState.equals(stateBefore))
              console.error(`${resourceName} UPDATED BUT EQUAL!`)
            else console.info(`${resourceName} updated`)
        }
        if (deletedIDs) {
          console.error({ deletedIDs, simple, lookupByID })
          // FIXME: Support this for resources with complicated
          //        (non-unique) ids.
          if (simple) {
            if (table === byID) {
              newState = newState.withMutations(
                (state: Immutable.Map<any, any>) => {
                  for (const itemID of deletedIDs) {
                    state.delete(itemID)
                  }
                }
              )
              //newState = newState.deleteAll(deletedIDs)
            }
          } else if (lookupByID) {
            for (const deletedID of deletedIDs) {
              const item = lookupByID(state, deletedID)
              console.error({ deletedID, item })
              for (const tableName of Object.keys(table)) {
                for (const { key } of (table as ComplexTable)[tableName](
                  item
                )) {
                  newState = newState.deleteIn([tableName, key])
                }
              }
            }
          }
        }
        if (invalidIDs) {
          if (simple) {
            if (table === byID) {
              newState = newState.withMutations(
                (state: Immutable.Map<any, any>) => {
                  for (const itemID of invalidIDs) {
                    state.set(itemID, new InvalidItem(itemID))
                  }
                }
              )
            }
          } else if (lookupByID) {
            for (const tableName of Object.keys(table)) {
              if ((table as ComplexTable)[tableName] === byID) {
                for (const itemID of invalidIDs) {
                  newState = newState.setIn(
                    [tableName, itemID],
                    new InvalidItem(itemID)
                  )
                }
              }
            }
          }
        }
        return newState

      default:
        return state
    }
  }
  var finalReducer = mainReducer
  if (reducer) {
    finalReducer = (state, action) =>
      reducer(mainReducer(state, action), action)
  }
  //finalReducer.recordType = recordType
  return finalReducer
}
