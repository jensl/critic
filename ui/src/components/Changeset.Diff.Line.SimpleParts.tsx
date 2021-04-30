import React from "react"
import clsx from "clsx"

import Registry from "."
import {
  kNeutralPartType,
  kNeutralPartState,
  kDeletedPartState,
  kInsertedPartState,
  kTokenTypes,
  Part,
  kIdentifierPartType,
} from "../resources/diffcommon"

type ContentItem = null | string | JSX.Element
type Content = ContentItem | ContentItem[]

type PartsProps = {
  content: readonly Part[]
  side: "old" | "new" | null
}

const renderPart = (part: Part, isOldSide: boolean, index: number): Content => {
  const { content, type, state } = part
  if (type === kNeutralPartType && state === kNeutralPartState) return content
  if (isOldSide ? state > 0 : state < 0) return null
  return (
    <span
      key={index}
      className={clsx(
        kTokenTypes[type],
        state === kDeletedPartState && "deleted",
        state === kInsertedPartState && "inserted",
      )}
    >
      {content}
      {type !== kIdentifierPartType && <wbr />}
    </span>
  )
}

const Parts: React.FunctionComponent<PartsProps> = ({ content, side }) => {
  const isOldSide = side === "old"

  return <>{content.map((part, index) => renderPart(part, isOldSide, index))}</>
}

// export default Registry.add("Changeset.Diff.Line.SimpleParts", React.memo(Parts))

export default React.memo(Parts)
