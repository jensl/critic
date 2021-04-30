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

import { immerable } from "immer"

import { primaryMap } from "../reducers/resource"
import { ExtensionVersionID } from "./types"

type ExtensionVersionData = {
  id: ExtensionVersionID
  extension: number
  name: string
  sha1: null | string
  description: string
  authors: AuthorData[]
}

type ExtensionVersionProps = {
  id: ExtensionVersionID
  extension: number
  name: string
  sha1: null | string
  description: string
  authors: readonly Author[]
}

class ExtensionVersion {
  [immerable] = true

  constructor(
    readonly id: ExtensionVersionID,
    readonly extension: number,
    readonly name: string,
    readonly sha1: null | string,
    readonly description: string,
    readonly authors: readonly Author[],
  ) {}

  static new(props: ExtensionVersionProps) {
    return new ExtensionVersion(
      props.id,
      props.extension,
      props.name,
      props.sha1,
      props.description,
      props.authors,
    )
  }

  static prepare(value: ExtensionVersionData): ExtensionVersionProps {
    return {
      ...value,
      authors: value.authors.map(Author.make),
    }
  }

  static reducer = primaryMap<ExtensionVersion, ExtensionVersionID>(
    "extensionversions",
  )

  get props() {
    return this
  }
}

type AuthorData = {
  name: string
  email: string | null
}

type AuthorProps = AuthorData

export class Author {
  [immerable] = true

  constructor(readonly name: string, readonly email: string | null) {}

  static new(props: AuthorProps) {
    return new Author(props.name, props.email)
  }

  static make(value: AuthorData) {
    return Author.new(value)
  }

  get props(): AuthorProps {
    return this
  }
}

export default ExtensionVersion
