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

import { primaryMap } from "../reducers/resource"
import { MacroChunk, MacroChunkData } from "./filediff"
import { ChangesetID, CommitID, FileID } from "./types"

type MergeAnalysisData = {
  merge: CommitID
  changes_relative_parents: ChangesRelativeParentData[]
  conflict_resolutions: ChangesetID
}

type MergeAnalysisProps = {
  merge: CommitID
  changes_relative_parents: ChangesRelativeParent[]
  conflict_resolutions: ChangesetID
}

class MergeAnalysis {
  constructor(
    readonly merge: CommitID,
    readonly changesRelativeParents: ChangesRelativeParent[],
    readonly conflictResolutions: ChangesetID
  ) {}

  static new(props: MergeAnalysisProps) {
    return new MergeAnalysis(
      props.merge,
      props.changes_relative_parents,
      props.conflict_resolutions
    )
  }

  static prepare(value: MergeAnalysisData): MergeAnalysisProps {
    return {
      ...value,
      changes_relative_parents: ChangesRelativeParent.make(
        value.changes_relative_parents
      ),
    }
  }

  static reducer = primaryMap<MergeAnalysis, number>(
    "mergeanalyses",
    (analysis) => analysis.merge
  )

  get props(): MergeAnalysisProps {
    return {
      ...this,
      changes_relative_parents: this.changesRelativeParents,
      conflict_resolutions: this.conflictResolutions,
    }
  }
}

type ChangesRelativeParentData = {
  parent: CommitID
  files: FileID[]
  macro_chunks: Map<FileID, MacroChunkData[]>
}

type ChangesRelativeParentProps = {
  parent: number
  files: FileID[]
  macro_chunks: Map<FileID, MacroChunk[]>
}

class ChangesRelativeParent {
  constructor(
    readonly parent: number,
    readonly files: FileID[],
    readonly macroChunks: Map<FileID, MacroChunk[]>
  ) {}

  static new(props: ChangesRelativeParentProps) {
    return new ChangesRelativeParent(
      props.parent,
      props.files,
      props.macro_chunks
    )
  }

  static make(changes_relative_parents: ChangesRelativeParentData[]) {
    function* generate() {
      for (const value of changes_relative_parents) {
        yield ChangesRelativeParent.new({
          ...value,
          macro_chunks: new Map(
            Object.entries(value.macro_chunks).map(([fileID, macroChunks]) => {
              return [parseInt(fileID, 10), MacroChunk.make(macroChunks)]
            })
          ),
        })
      }
    }
    return Array.from(generate())
  }
}

export default MergeAnalysis
