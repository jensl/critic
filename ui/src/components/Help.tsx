import React, { FunctionComponent } from "react"

import Container from "@material-ui/core/Container"

import MarkdownDocument from "./Markdown.Document"

type OwnProps = {
  className?: string
}

const Help: FunctionComponent<OwnProps> = ({ className }) => (
  <Container maxWidth="md" className={className}>
    <MarkdownDocument>{`
# Help
`}</MarkdownDocument>
  </Container>
)

export default Help
