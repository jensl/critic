import FileDiff, {
  kContextLine,
  kDeletedLine,
  kInsertedLine,
} from "../resources/filediff"

export const countChangedLines = (filediff: FileDiff) => {
  var deleted = 0
  var inserted = 0

  for (const macroChunk of filediff.macroChunks)
    for (const line of macroChunk.content)
      if (line.type !== kContextLine) {
        if (line.type !== kDeletedLine) ++inserted
        if (line.type !== kInsertedLine) ++deleted
      }

  return { deleted, inserted }
}
