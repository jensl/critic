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

type FileContentProps = {
  repository: RepositoryID
  file: FileID
  sha1: string
  lines: any[]
}

class FileContent {
  [immerable] = true

  constructor(
    readonly repository: RepositoryID,
    readonly file: FileID,
    readonly sha1: string,
    readonly lines: any[],
  ) {}

  static new(props: FileContentProps) {
    return new FileContent(
      props.repository,
      props.file,
      props.sha1,
      props.lines,
    )
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
