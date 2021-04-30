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

import { BoundingRect } from "../actions"

export const all = <T>(items: Iterable<T>, predicate: (v: T) => boolean) => {
  for (const v of items) if (!predicate(v)) return false
  return true
}

export const any = <T>(items: Iterable<T>, predicate: (v: T) => boolean) => {
  for (const v of items) if (predicate(v)) return true
  return false
}

export const count = <T>(items: Iterable<T>, predicate: (v: T) => boolean) => {
  let count = 0
  for (const v of items) if (predicate(v)) ++count
  return count
}

export const sum = <T>(items: Iterable<T>, reducer: (v: T) => number) => {
  let sum = 0
  for (const v of items) sum += reducer(v)
  return sum
}

export const soon = (fn: () => void) => setTimeout(fn, 0)

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

export const id = <T extends ObjectWithID>(object: T | null | undefined) =>
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

export const setWithoutAll = <T>(
  set: ReadonlySet<T>,
  items: ReadonlySet<T>,
): ReadonlySet<T> => filteredSet(set, (item) => items.has(item))

export function* filtered<T>(
  items: Iterable<T>,
  predicate: (item: T) => boolean,
): IterableIterator<T> {
  for (const item of items) if (predicate(item)) yield item
}

export function* filterNulls<T>(
  items: Iterable<T | null | undefined>,
): IterableIterator<T> {
  for (const item of items) if (item !== null && item !== undefined) yield item
}

export const filteredSet = <T>(
  items: Iterable<T>,
  predicate: (item: T) => boolean,
): ReadonlySet<T> => new Set(filtered(items, predicate))

export const mappedSet = <T, U>(
  items: Iterable<T>,
  mapper: (item: T) => U,
): ReadonlySet<U> => new Set([...items].map(mapper))

export const mergedSets = <T>(...items: Iterable<T>[]): ReadonlySet<T> =>
  new Set(items.flatMap((iterable) => [...iterable]))

export const identicalSets = <T>(a: ReadonlySet<T>, b: ReadonlySet<T>) => {
  if (a.size !== b.size) return false
  const merged = new Set([...a, ...b])
  return merged.size === a.size
}

export const filterInPlace = <T>(
  items: T[],
  predicate: (item: T) => boolean,
): T[] => {
  const filtered = items.filter(predicate)
  if (filtered.length < items.length) {
    items.length = filtered.length
    for (let index = 0; index < items.length; ++index)
      items[index] = filtered[index]
  }
  return items
}

export const outerBoundingRect = (
  rects: Iterable<BoundingRect>,
): BoundingRect => {
  let topMin = Number.MAX_SAFE_INTEGER
  let rightMax = Number.MIN_SAFE_INTEGER
  let bottomMax = Number.MIN_SAFE_INTEGER
  let leftMin = Number.MAX_SAFE_INTEGER

  for (const { top, right, bottom, left } of rects) {
    if (top < topMin) topMin = top
    if (right > rightMax) rightMax = right
    if (bottom > bottomMax) bottomMax = bottom
    if (left < leftMin) leftMin = left
  }

  const top = topMin + window.scrollY
  const right = rightMax + window.scrollX
  const bottom = bottomMax + window.scrollY
  const left = leftMin + window.scrollX

  return { top, right, bottom, left }
}

export function* chain<T>(...items: Iterable<T>[]) {
  for (const someItems of items) for (const item of someItems) yield item
}
