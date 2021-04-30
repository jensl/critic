import React, { FunctionComponent } from "react"
import clsx from "clsx"

import Registry from "."
import Parts from "./Changeset.Diff.Line.SimpleParts"
import { DiffLine } from "../resources/diffcommon"

type Props = {
  className?: string
  lineID: string
  line: DiffLine | null
  side?: "old" | "new" | null
  isSelected: boolean
  hasSelection: boolean
  inView: boolean
}

const ChangesetLine: FunctionComponent<Props> = ({
  className,
  lineID,
  line,
  side = null,
  isSelected,
  hasSelection,
  inView,
}: Props) => {
  if (line === null) return <span className={clsx(className)} />
  return (
    <span
      className={clsx(className, "code", {
        selected: isSelected,
        unselected: hasSelection && !isSelected,
      })}
      data-line-id={lineID}
    >
      {inView ? (
        <Parts content={line.content} side={side} />
      ) : side === "old" ? (
        line.oldPlain
      ) : (
        line.newPlain
      )}
    </span>
  )
}

// export default Registry.add("Changeset.Diff.Line", React.memo(ChangesetLine))

export default React.memo(ChangesetLine)
