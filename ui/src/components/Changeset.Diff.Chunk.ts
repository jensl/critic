import { MacroChunk } from "../resources/filediff"
import { ChangesetID, FileID } from "../resources/types"
import { SelectionScope } from "../reducers/uiSelectionScope"
import { ChunkComments } from "../selectors/fileDiff"

export type ChunkProps = {
  className?: string
  changesetID: ChangesetID
  fileID: FileID
  scopeID: string
  chunk: MacroChunk
  comments: ChunkComments | null
  selectionScope: SelectionScope | null
  inView: boolean
}
