import React, { FunctionComponent } from "react"
import clsx from "clsx"

import Registry from "."
import Parts from "./Changeset.Diff.Line.SimpleParts"
import { DiffLine, Part } from "../resources/filediff"
import { pure } from "recompose"

type Props = {
  className?: string
  lineID: string
  line: DiffLine | null
  side?: "old" | "new" | null
  isSelected?: boolean
  inView: boolean
}

const ChangesetLine: FunctionComponent<Props> = ({
  className,
  lineID,
  line,
  side = null,
  isSelected = false,
  inView,
}: Props) => {
  if (line === null) return <span className={clsx(className)} />

  return (
    <span
      className={clsx(className, "code", { selected: isSelected })}
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

export default Registry.add("Changeset.Diff.Line", pure(ChangesetLine))
