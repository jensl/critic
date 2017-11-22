import React, { useEffect } from "react"

import Container from "@material-ui/core/Container"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import MarkdownDocument from "./Markdown.Document"
import { download } from "../actions/download"
import { useDispatch, useSelector } from "../store"
import { useRepository, useResource } from "../utils"
import { makeStyles } from "@material-ui/core"

const useStyles = makeStyles((theme) => ({
  container: {},

  path: {
    fontFamily: "Source Code Pro, monospace",
    fontSize: "2rem",
    fontWeight: 500,
    marginTop: theme.spacing(4),
    paddingBottom: theme.spacing(1),
    borderBottom: "1px solid rgba(0, 0, 0, 0.1)",
    marginBottom: theme.spacing(4),
  },
}))

const RepositoryDocumentation: React.FunctionComponent = () => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const repository = useRepository()
  const commit = useResource("commits", (commits) =>
    commits.byID.get((repository && repository.head.commit) || -1)
  )
  const contents = useSelector((state) =>
    repository && commit && repository.documentation_path
      ? state.download.get(
          `${repository.id}:${commit.id}:${repository.documentation_path}`
        )
      : null
  )
  useEffect(() => {
    if (repository && commit && repository.documentation_path && !contents) {
      dispatch(
        download(repository.id, commit.id, repository.documentation_path)
      )
    }
  }, [dispatch, repository, commit, contents])
  if (!repository || !contents) return null
  return (
    <Container maxWidth="md" className={classes.container}>
      <Typography variant="h1" className={classes.path}>
        {repository.documentation_path}
      </Typography>
      <MarkdownDocument source={contents} />
    </Container>
  )
}

export default Registry.add("Repository.Documentation", RepositoryDocumentation)
