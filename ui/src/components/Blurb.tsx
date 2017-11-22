import React from "react"
import clsx from "clsx"

import Container from "@material-ui/core/Container"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import MarkdownDocument from "./Markdown.Document"

const useStyles = makeStyles((theme) => ({
  blurb: {
    padding: theme.spacing(0.5, 4),
    backgroundColor: theme.palette.secondary.light,
    border: "1px solid",
    borderColor: theme.palette.secondary.main,
    borderRadius: theme.spacing(1),
  },
}))

type Props = {
  className?: string
  text: string
}

const Blurb: React.FunctionComponent<Props> = ({ className, text }) => {
  const classes = useStyles()
  return (
    <Container className={clsx(className, classes.blurb)} maxWidth="sm">
      <MarkdownDocument>{text}</MarkdownDocument>
    </Container>
  )
}

export default Registry.add("Blurb", Blurb)
