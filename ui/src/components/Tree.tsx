import React, { useState } from "react"

import { makeStyles, withStyles } from "@material-ui/core/styles"
import TreeView from "@material-ui/lab/TreeView"
import MuiTreeItem from "@material-ui/lab/TreeItem"
import FolderIcon from "@material-ui/icons/Folder"
import Container from "@material-ui/core/Container"

import Registry from "."
import {
  useSubscriptionIf,
  useRepository,
  useResource,
  useResourceExtra,
  any,
} from "../utils"
import { loadTree } from "../actions/tree"
import { RepositoryID, CommitID } from "../resources/types"
import Commit from "../resources/commit"
import { Entry as TreeEntry } from "../resources/tree"

const useStyles = makeStyles((theme) => ({
  entry: {},

  fileLabel: { display: "flex" },
  name: { flexGrow: 1 },
  size: { flexGrow: 0, opacity: "80%" },
}))

const TreeItem = withStyles((theme) => ({
  root: {
    paddingTop: "3px",
    paddingBottom: "3px",
  },
  label: {
    ...theme.critic.monospaceFont,
  },
}))(MuiTreeItem)

type Props = {
  className?: string
  commit?: Commit
  path?: string
}

const useTree = (
  repositoryID: RepositoryID,
  commitID: CommitID,
  path: string,
) => {
  const key = useResourceExtra("trees", (trees) =>
    trees.byCommitPath.get(`${repositoryID}:${commitID}:${path}`),
  )
  return useResource("trees", (trees) => trees.get(key || ""))
}

const Fetch: React.FunctionComponent<{
  repositoryID: RepositoryID
  commitID: CommitID
  path: string
}> = ({ repositoryID, commitID, path }) => {
  const tree = useTree(repositoryID, commitID, path)
  useSubscriptionIf(!tree, loadTree, repositoryID, commitID, path)
  return null
}

type P = {
  classes: ReturnType<typeof useStyles>
  repositoryID: RepositoryID
  commitID: CommitID
  path: string
  expanded: string[]
}

const Entry: React.FunctionComponent<P & { entry: TreeEntry }> = ({
  entry,
  path,
  ...props
}) => {
  const { name, size } = entry
  path = path ? `${path}/${name}` : name
  const childProps = { ...props, path, name, size }
  return isDir(entry) ? <Directory {...childProps} /> : <File {...childProps} />
}

const isDir = (entry: TreeEntry) => (entry.mode & 0x4000) === 0x4000
const Entries: React.FunctionComponent<P> = (props) => {
  const { repositoryID, commitID, path } = props
  const tree = useTree(repositoryID, commitID, path)
  const compare = (a: TreeEntry, b: TreeEntry) => {
    if (isDir(a)) {
      if (!isDir(b)) return -1
    } else if (isDir(b)) return 1
    return a.name < b.name ? -1 : a.name > b.name ? 1 : 0
  }
  return tree ? (
    <>
      {[...tree.entries].sort(compare).map((entry) => (
        <Entry key={entry.name} entry={entry} {...props} />
      ))}
    </>
  ) : (
    <TreeItem nodeId={`${path}/...`} label="..." />
  )
}

const File: React.FunctionComponent<P & { name: string; size: number }> = ({
  classes,
  path,
  name,
  size,
}) => (
  <TreeItem
    className={classes.entry}
    nodeId={path}
    label={
      <span className={classes.fileLabel}>
        <span className={classes.name}>{name}</span>
        <span className={classes.size}>{size} bytes</span>
      </span>
    }
  />
)

const Directory: React.FunctionComponent<P & { name?: string }> = ({
  name,
  expanded,
  ...props
}) => {
  const { path } = props
  const entries = (
    <>
      {expanded.includes(path) ? <Fetch {...props} /> : null}
      <Entries {...props} expanded={expanded} />
    </>
  )
  return name ? (
    <TreeItem nodeId={path} label={name} icon={<FolderIcon />}>
      {entries}
    </TreeItem>
  ) : (
    <>{entries}</>
  )
}

const updateExpanded = (currentExpanded: string[], nextExpanded: string[]) => {
  const currentSet = new Set(currentExpanded)
  const newIDs: string[] = []
  for (const nodeID of nextExpanded) {
    if (!currentSet.has(nodeID)) newIDs.push(nodeID)
  }
  return newIDs.length
    ? nextExpanded.filter((nodeID) =>
        any(newIDs, (newID) => newID.startsWith(nodeID)),
      )
    : nextExpanded
}

const Tree: React.FunctionComponent<Props> = ({ className, commit, path }) => {
  const classes = useStyles()
  const repository = useRepository()
  const [expanded, setExpanded] = useState<string[]>([""])
  if (!repository) return null
  const commitID = commit?.id ?? repository.head?.commit
  if (typeof commitID !== "number") return null
  return (
    <Container maxWidth="md">
      <TreeView
        expanded={expanded}
        onNodeToggle={(ev, nodeIDs) =>
          setExpanded(updateExpanded(expanded, nodeIDs))
        }
      >
        <Directory
          classes={classes}
          repositoryID={repository.id}
          commitID={commitID}
          path={""}
          expanded={expanded}
        />
      </TreeView>
    </Container>
  )
}

export default Registry.add("Tree", Tree)
