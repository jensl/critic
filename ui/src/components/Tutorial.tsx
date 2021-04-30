import React, { FunctionComponent } from "react"
import { connect } from "react-redux"
import { RouteComponentProps } from "react-router"

import Container from "@material-ui/core/Container"

import Registry from "."
import MarkdownDocument from "./Markdown.Document"
import LoaderBlock from "./Loader.Block"
import { useSubscription } from "../utils"
import { State } from "../state"
import { loadTutorial } from "../actions/tutorial"
import * as S from "../resources/statetypes"

type Params = {
  tutorialID: string
}

type OwnProps = {
  className?: string
  tutorials: S.Tutorial
}

const Tutorial: FunctionComponent<OwnProps & RouteComponentProps<Params>> = ({
  className,
  match,
  tutorials,
}) => {
  const { tutorialID } = match.params
  useSubscription(loadTutorial, [tutorialID])
  const tutorial = tutorials.get(tutorialID)
  if (!tutorial) return <LoaderBlock />
  return (
    <Container className={className} maxWidth="md">
      <MarkdownDocument source={tutorial.source} />
    </Container>
  )
}

export default Registry.add(
  "Tutorial",
  connect((state: State) => ({ tutorials: state.resource.tutorials }))(
    Tutorial,
  ),
)
