import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Progress from "./Commit.ListItem.Progress"
import Summary from "./Commit.ListItem.Summary"
import SHA1 from "./Commit.ListItem.SHA1"
import Metadata from "./Commit.ListItem.Metadata"
import Reviewers from "./Commit.ListItem.Reviewers"
import ChangedLines from "./Commit.ListItem.ChangedLines"
import { useResource } from "../utils"
import { SelectionScope } from "../reducers/uiSelectionScope"

const useStyles = makeStyles((theme) => ({
  commitListitem: {
    display: "grid",
    padding: `${theme.spacing(1)}px ${theme.spacing(2)}px`,
    //margin: `${theme.spacing(1)}px 0`,

    "&:hover": {
      background: theme.palette.secondary.light,
      cursor: "pointer",
      borderRadius: 4,
    },

    "& > *": { alignSelf: "center" },
  },
  selected: {
    background: theme.palette.secondary.light,
    "&:hover": {
      background: theme.palette.secondary.main,
      borderRadius: 0,
    },
  },
  firstSelected: {
    borderTopLeftRadius: 4,
    borderTopRightRadius: 4,
    "&:hover": {
      borderTopLeftRadius: 4,
      borderTopRightRadius: 4,
    },
  },
  lastSelected: {
    borderBottomLeftRadius: 4,
    borderBottomRightRadius: 4,
    "&:hover": {
      borderBottomLeftRadius: 4,
      borderBottomRightRadius: 4,
    },
  },

  [theme.breakpoints.up("sm")]: {
    withProgress: {
      gridTemplateRows: "1fr 1fr",
      gridTemplateColumns: "4rem 1fr 2fr 8rem",
      gridTemplateAreas: `
      "progress summary summary sha1"
      "progress metadata reviewers lines"
    `,
    },
    withoutProgress: {
      gridTemplateRows: "1fr 1fr",
      gridTemplateColumns: "1fr 8rem",
      gridTemplateAreas: `
      "summary sha1"
      "metadata lines"
    `,
    },
  },

  [theme.breakpoints.down("sm")]: {
    withProgress: {
      gridTemplateRows: "1fr 1fr auto",
      gridTemplateColumns: "1fr auto",
      gridTemplateAreas: `
      "summary sha1"
      "metadata lines"
      "progress progress"
    `,
    },
    withoutProgress: {
      gridTemplateRows: "1fr 1fr",
      gridTemplateColumns: "1fr 8rem",
      gridTemplateAreas: `
      "summary sha1"
      "metadata lines"
    `,
    },
  },

  popup: {
    marginBottom: "1rem",
    padding: "0.2rem 0.5rem",
    background: theme.palette.secondary.main,
  },
}))

type Props = {
  className?: string
  commitID: number
  withProgress?: boolean
  selectionScope: SelectionScope | null
}

const CommitListItem: FunctionComponent<Props> = ({
  className,
  commitID,
  withProgress,
  selectionScope,
}) => {
  const classes = useStyles()
  const commit = useResource("commits", (commits) => commits.byID.get(commitID))

  if (!commit) return null

  const elementID = String(commitID)
  const isSelected = selectionScope?.selectedIDs.has(elementID) ?? false
  const isFirstSelected = elementID === selectionScope?.firstSelectedID
  const isLastSelected = elementID === selectionScope?.lastSelectedID

  return (
    <div
      className={clsx(className, classes.commitListitem, {
        [classes.withProgress]: withProgress,
        [classes.withoutProgress]: !withProgress,
        [classes.selected]: isSelected,
        [classes.firstSelected]: isFirstSelected,
        [classes.lastSelected]: isLastSelected,
      })}
      data-commit-id={commit.id}
    >
      {withProgress && <Progress commit={commit} />}
      <Summary commit={commit} />
      <SHA1 commit={commit} />
      <Metadata commit={commit} />
      <Reviewers commit={commit} />
      <ChangedLines commit={commit} />
    </div>
  )
}

export default Registry.add("Commit.ListItem", CommitListItem)