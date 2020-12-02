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

import { immerable } from "immer"

import { primaryMap } from "../reducers/resource"

type TreeData = {
  repository: number
  sha1: string
  entries: EntryData[]
}

type TreeProps = {
  repository: number
  sha1: string
  entries: Entry[]
}

export class Tree {
  [immerable] = true

  constructor(
    readonly repository: number,
    readonly sha1: string,
    readonly entries: Entry[],
  ) {}

  static new(props: TreeProps) {
    return new Tree(props.repository, props.sha1, props.entries)
  }

  static prepare(value: TreeData): TreeProps {
    return {
      ...value,
      entries: value.entries.map(Entry.new),
    }
  }

  static reducer = primaryMap<Tree, string>(
    "trees",
    (tree) => `${tree.repository}:${tree.sha1}`,
  )

  get props(): TreeProps {
    return this
  }
}

type EntryData = {
  mode: number
  name: string
  sha1: string
  size: number
  target: string | null
}

type EntryProps = EntryData

export class Entry {
  [immerable] = true

  constructor(
    readonly mode: number,
    readonly name: string,
    readonly sha1: string,
    readonly size: number,
    readonly target: string | null,
  ) {}

  static new(props: EntryProps) {
    return new Entry(
      props.mode,
      props.name,
      props.sha1,
      props.size,
      props.target,
    )
  }
}

export default Tree
