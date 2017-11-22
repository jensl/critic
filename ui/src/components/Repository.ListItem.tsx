import React, { FunctionComponent } from "react"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Title from "./Repository.ListItem.Title"
import Metadata from "./Repository.ListItem.Metadata"
import { RepositoryID } from "../resources/types"
import { useResource } from "../utils"

const useStyles = makeStyles((theme) => ({
  repositoryListItem: {
    display: "grid",
    paddingTop: theme.spacing(1),
    paddingBottom: theme.spacing(1),
    [theme.breakpoints.up("md")]: {
      gridTemplateRows: "1fr 1fr",
      gridTemplateColumns: "4rem 1fr",
      gridTemplateAreas: `
        "progress title"
        "progress metadata"
      `,
      paddingLeft: theme.spacing(2),
      paddingRight: theme.spacing(2),
    },
    [theme.breakpoints.down("sm")]: {
      gridTemplateRows: "auto",
      gridTemplateColumns: "1fr",
      gridTemplateAreas: `
        "title"
        "metadata"
      `,
      paddingLeft: theme.spacing(0.5),
      paddingRight: theme.spacing(0.5),
    },
    textDecoration: "none",
    color: "inherit",

    "&:hover": {
      background: theme.palette.secondary.light,
      cursor: "pointer",
      borderRadius: 4,
    },
  },
}))

type OwnProps = {
  className?: string
  repositoryID: RepositoryID
}

const RepositoryListItem: FunctionComponent<OwnProps> = ({
  className,
  repositoryID,
}) => {
  const classes = useStyles()
  const repository = useResource("repositories").byID.get(repositoryID)
  if (!repository) return null
  return (
    <Link
      to={`/repository/${repository.name}`}
      className={clsx(className, classes.repositoryListItem)}
    >
      <Title repository={repository} />
      <Metadata repository={repository} />
    </Link>
  )
}

export default Registry.add("Repository.ListItem", RepositoryListItem)
