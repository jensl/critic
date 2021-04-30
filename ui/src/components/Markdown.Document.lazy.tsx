import React, { FunctionComponent, useEffect, useState } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import BlockContent from "./Markdown.BlockContent"
import Markdown, { Document } from "../utils/Markdown"
import { textFromChildren } from "../utils/Strings"

const useStyles = makeStyles((theme) => ({
  markdownDocument: {
    margin: theme.spacing(1, 0),
  },
}))

type OwnProps = {
  className?: string
  source?: string
  summary?: boolean
}

const MarkdownDocument: FunctionComponent<OwnProps> = ({
  className,
  source,
  summary = false,
  children,
}) => {
  const classes = useStyles()
  const [document, setDocument] = useState<Document | null>(null)

  const effectiveSource = source ?? textFromChildren(children)

  useEffect(() => {
    setDocument(Markdown.parse(effectiveSource))
  }, [effectiveSource])

  if (!document) return null

  const content = summary ? document.content.slice(0, 1) : document.content

  return (
    <div className={clsx(className, classes.markdownDocument)}>
      <BlockContent content={content} />
    </div>
  )
}

export default MarkdownDocument
