import React from "react"
import clsx from "clsx"

import ArrowRightAltIcon from "@material-ui/icons/ArrowRightAlt"

import {
  kNeutralPartType,
  kNeutralPartState,
  kDeletedPartState,
  kInsertedPartState,
  kTokenTypes,
  Part,
} from "../resources/diffcommon"

type ContentItem = null | string | JSX.Element
type Content = ContentItem | ContentItem[]

type PartsProps = {
  content: readonly Part[]
  side: "old" | "new" | null
}

const Parts: React.FunctionComponent<PartsProps> = ({ content, side }) => {
  const tabSize = 4

  const tabify = (fragment: string, offset: number): [Content, number] => {
    const parts = fragment.split(/(\t)/)
    if (parts.length === 1) return [fragment, fragment.length]
    const offsetBefore = offset
    return [
      parts.map((part: string) => {
        if (!part) return null
        if (part === "\t") {
          const thisTabSize = tabSize - (offset % tabSize) || tabSize
          offset += tabSize
          return (
            <ArrowRightAltIcon key={offset} className={`tab w${thisTabSize}`} />
          )
        }
        offset += part.length
        return part
      }),
      offset - offsetBefore,
    ]
  }

  const renderPart = (
    part: Part,
    isOldSide: boolean,
    index: number,
    offset: number,
  ): [Content, number] => {
    const { content, type, state } = part
    const maybeTabify = (): [Content, number] =>
      partType === "chr" || partType === "str" || partType === "com"
        ? tabify(content, offset)
        : [content, content.length]
    if (type === kNeutralPartType && state === kNeutralPartState)
      return tabify(content, offset)
    if (isOldSide ? state > 0 : state < 0) return [null, 0]
    const partClasses = []
    const partType = kTokenTypes[type]
    if (partType) partClasses.push(partType)
    if (state === kDeletedPartState) partClasses.push("deleted")
    else if (state === kInsertedPartState) partClasses.push("inserted")
    let wordBreak = null
    if (partType !== "id") wordBreak = <wbr />
    const [tabifiedContent, length] = maybeTabify()
    return [
      <span key={index} className={clsx(partClasses)} data-offset={offset}>
        {tabifiedContent}
        {wordBreak}
      </span>,
      length,
    ]
  }

  const isOldSide = side === "old"
  let offset = 0

  return (
    <>
      {content.map((part, index) => {
        const [rendered, length] = renderPart(part, isOldSide, index, offset)
        offset += length
        return rendered
      })}
    </>
  )
}

// export default Registry.add("Changeset.Diff.Line.SimpleParts", React.memo(Parts))

export default React.memo(Parts)
