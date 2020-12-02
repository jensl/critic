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

type FileChangeProps = {
  file: number
  changeset: number
  old_sha1: string | null
  old_mode: string | null
  new_sha1: string | null
  new_mode: string | null
}

class FileChange {
  [immerable] = true

  constructor(
    readonly file: number,
    readonly changeset: number,
    readonly oldSha1: string | null,
    readonly oldMode: string | null,
    readonly newSha1: string | null,
    readonly newMode: string | null,
  ) {}

  static new(props: FileChangeProps) {
    return new FileChange(
      props.file,
      props.changeset,
      props.old_sha1,
      props.old_mode,
      props.new_sha1,
      props.new_mode,
    )
  }

  static reducer = primaryMap<FileChange, string>(
    "filechanges",
    (filechange) => `${filechange.changeset}:${filechange.file}`,
  )

  get props(): FileChangeProps {
    return {
      ...this,
      old_sha1: this.oldSha1,
      old_mode: this.oldMode,
      new_sha1: this.newSha1,
      new_mode: this.newMode,
    }
  }

  get wasDeleted() {
    return this.newSha1 === null
  }
  get wasAdded() {
    return this.oldSha1 === null
  }
}

export default FileChange
