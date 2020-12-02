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

export const all = <T>(items: T[], predicate: (v: T) => boolean) =>
  items.reduce((value, item) => value && !!predicate(item), true)

export const any = <T>(items: Iterable<T>, predicate: (v: T) => boolean) => {
  for (const v of items) if (predicate(v)) return true
  return false
}

export const count = <T>(items: T[], predicate: (v: T) => boolean) =>
  items.reduce((value, item) => value + Number(predicate(item)), 0)

export const sum = <T>(items: T[], reducer: (v: T) => number) =>
  items.reduce((accumulator, item) => accumulator + reducer(item), 0)

type SoonCallback = <T extends any[]>(args: T) => void

// Call function "soon", and ignore repeated calls while one call is pending.
export const soon = (fn: SoonCallback): SoonCallback => {
  var callPending = false
  return (...args) => {
    if (!callPending) {
      callPending = true
      setTimeout(() => {
        callPending = false
        fn(...args)
      }, 0)
    }
  }
}

export const safe = (object: any) =>
  object || new Proxy({}, { get: () => null })

type ObjectWithID = { id: any }

export function getProperty<T, K extends keyof T>(
  object: T | null | undefined,
  key: K,
): T[K] | undefined
export function getProperty<T, K extends keyof T>(
  object: T | null | undefined,
  key: K,
  defaultValue: T[K],
): T[K]

export function getProperty<T, K extends keyof T>(
  object: T | null,
  key: K,
  defaultValue?: T[K],
) {
  return object ? object[key] : defaultValue
}

export const id = <T extends ObjectWithID>(object: T | null) =>
  getProperty(object, "id", -1)

export const compareByProps = <T, K extends keyof T>(...props: K[]) => (
  A: T,
  B: T,
) => {
  for (const prop of props) {
    const a = A[prop]
    const b = B[prop]
    if (a < b) return -1
    else if (a > b) return 1
  }
  return 0
}

export const sleep = (durationMS: number) =>
  new Promise((resolve) => {
    setTimeout(resolve, durationMS)
  })

export const map = <T, U>(
  items: Iterable<T>,
  callback: (item: T) => U,
): U[] => {
  const result: U[] = []
  for (const item of items) result.push(callback(item))
  return result
}

export const sorted = <T>(items: Iterable<T>): T[] => [...items].sort()

export const sortedBy = <T, K extends number | string>(
  items: Iterable<T>,
  key: (item: T) => K,
): T[] =>
  [...items].sort((a, b) => {
    const aKey = key(a)
    const bKey = key(b)
    switch (true) {
      case aKey < bKey:
        return -1
      case aKey > bKey:
        return 1
      default:
        return 0
    }
  })

export const setWith = <T>(set: ReadonlySet<T>, item: T): ReadonlySet<T> => {
  if (set.has(item)) return set
  const result = new Set(set)
  result.add(item)
  return result
}

export const setWithout = <T>(set: ReadonlySet<T>, item: T): ReadonlySet<T> => {
  if (!set.has(item)) return set
  const result = new Set(set)
  result.delete(item)
  return result
}

export const filteredSet = <T>(
  items: Iterable<T>,
  predicate: (item: T) => boolean,
): ReadonlySet<T> => new Set([...items].filter(predicate))

export const mergedSets = <T>(...items: Iterable<T>[]): ReadonlySet<T> =>
  new Set(items.flatMap((iterable) => [...iterable]))
