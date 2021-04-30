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
import { FileID, RepositoryID } from "./types"
import { DiffLine, kContextLine, PartData } from "./diffcommon"
import { map } from "../utils/Functions"

type FileContentData = {
  repository: RepositoryID
  sha1: string
  file: FileID | null
  offset: number
  lines: PartData[][]
}

type FileContentProps = {
  repository: RepositoryID
  file: FileID | null
  sha1: string
  lines: readonly DiffLine[]
}

class FileContent {
  [immerable] = true

  constructor(
    readonly repository: RepositoryID,
    readonly sha1: string,
    readonly file: FileID | null,
    readonly lines: readonly DiffLine[],
  ) {}

  static new(props: FileContentProps) {
    return new FileContent(
      props.repository,
      props.sha1,
      props.file,
      props.lines,
    )
  }

  static prepare(value: FileContentData): FileContentProps {
    return {
      ...value,
      lines: DiffLine.make(
        map(value.lines, (parts) => [kContextLine, parts]),
        value.offset,
        value.offset,
      ),
    }
  }

  static reducer = primaryMap<FileContent, string>(
    "filecontents",
    (filecontent) => `${filecontent.repository}:${filecontent.file}`,
  )

  get props(): FileContentProps {
    return this
  }
}

export default FileContent
