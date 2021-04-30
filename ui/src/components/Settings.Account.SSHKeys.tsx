import React, { FunctionComponent, useState, useEffect } from "react"

import TextField from "@material-ui/core/TextField"
import Button from "@material-ui/core/Button"
import Table from "@material-ui/core/Table"
import TableHead from "@material-ui/core/TableHead"
import TableBody from "@material-ui/core/TableBody"
import TableRow from "@material-ui/core/TableRow"
import TableCell from "@material-ui/core/TableCell"
import IconButton from "@material-ui/core/IconButton"
import DeleteIcon from "@material-ui/icons/Delete"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Section from "./Settings.Account.Section"
import Blurb from "./Blurb"
import Confirm from "./Dialog.Confirm"
import { loadUserSSHKeys, addSSHKey, deleteSSHKey } from "../actions/user"
import { useDispatch } from "../store"
import {
  useSignedInUser,
  useSubscriptionIf,
  id,
  useResource,
  sortedBy,
} from "../utils"
import UserSSHKey from "../resources/usersshkey"

const useStyles = makeStyles((theme) => ({
  accountSSHKeys: {
    paddingTop: theme.spacing(2),
    paddingBottom: theme.spacing(2),
    ...theme.mixins.gutters(),
  },
  blurb: {
    marginBottom: theme.spacing(2),
  },
  rawKeyInput: { ...theme.critic.monospaceFont },
  addKeyButton: {
    marginTop: theme.spacing(2),
    marginLeft: "auto",
    marginRight: "auto",
    marginBottom: theme.spacing(2),
    width: "20rem",
  },
  keysTable: { margin: theme.spacing(4, 3, 1, 3), width: "auto" },
  typeCell: {},
  keyType: { ...theme.critic.monospaceFont, fontWeight: 500 },
  fingerprintCell: { ...theme.critic.monospaceFont },
  titleCell: {},
}))

type ParsedSSHKey = {
  keyType: string
  keyData: string
  title: string
}

const parseKey = (
  rawKey: string,
): { parsedSSHKey?: ParsedSSHKey; errorMessage?: string } => {
  const match = /^\s*(\S+)\s+(\S+)(?:\s+(.+))?\s*$/.exec(rawKey)
  if (match) {
    const [, keyType, keyData, title] = match

    switch (keyType) {
      case "ssh-rsa":
      case "ssh-dss":
      case "ecdsa-sha2-nistp256":
      case "ssh-ed25519":
        try {
          window.atob(keyData)
        } catch (error) {
          return { errorMessage: "Invalid key data" }
        }
        return {
          parsedSSHKey: {
            keyType,
            keyData,
            title,
          },
        }
    }

    return { errorMessage: "Unsupported key type: " + keyType }
  }

  return { errorMessage: "Unrecognized key format" }
}

const AccountSSHKeys: FunctionComponent = () => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const user = useSignedInUser()
  const keys = useResource("usersshkeys")
  const [rawKey, setRawKey] = useState("")
  const [keyTitle, setKeyTitle] = useState("")
  const [selectedKey, setSelectedKey] = useState<UserSSHKey | null>(null)
  const [parsedSSHKey, setParsedSSHKey] = useState<ParsedSSHKey | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  useSubscriptionIf(user !== null, loadUserSSHKeys, [id(user)])
  useEffect(() => {
    if (!rawKey) {
      setErrorMessage(null)
      return
    }
    const { parsedSSHKey = null, errorMessage = null } = parseKey(rawKey)
    setParsedSSHKey(parsedSSHKey)
    setErrorMessage(errorMessage)

    if (parsedSSHKey && parsedSSHKey.title && !keyTitle)
      setKeyTitle(parsedSSHKey.title)
  }, [rawKey, keyTitle])
  if (user === null) return null
  const addKey = async () => {
    if (parsedSSHKey) {
      await dispatch(
        addSSHKey(
          user.id,
          parsedSSHKey.keyType,
          parsedSSHKey.keyData,
          keyTitle,
        ),
      )
      setRawKey("")
      setKeyTitle("")
    }
  }
  return (
    <Section id="ssh-keys" title="SSH keys">
      <Blurb className={classes.blurb}>
        SSH keys allow you to access Git repositories over SSH, without needing
        to type in your password or set up a Git credentials helper.
      </Blurb>
      <TextField
        InputProps={{ className: classes.rawKeyInput }}
        label="Public key"
        fullWidth
        margin="normal"
        multiline
        rows="10"
        id="rawkey"
        value={rawKey}
        onChange={(event) => setRawKey(event.target.value)}
        error={errorMessage !== null}
        helperText={
          errorMessage ||
          "The public key, typically found in a file named e.g. `id_rsa.pub`."
        }
        spellCheck={false}
        variant="outlined"
      />
      <TextField
        label="Title"
        fullWidth
        margin="normal"
        id="title"
        spellCheck={false}
        value={keyTitle}
        onChange={(event) => setKeyTitle(event.target.value)}
        variant="outlined"
        helperText="A title to help you identify which key this is."
      />
      <Button
        className={classes.addKeyButton}
        onClick={() => addKey()}
        color="primary"
        variant="contained"
        disabled={parsedSSHKey === null}
      >
        Add key
      </Button>
      {keys.size !== 0 && (
        <>
          <Table className={classes.keysTable}>
            <TableHead>
              <TableRow>
                <TableCell>Type / Length</TableCell>
                <TableCell>Fingerprint</TableCell>
                <TableCell>Title</TableCell>
                <TableCell size="small" />
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedBy(keys.values(), (key) => key.comment).map((key) => (
                <TableRow key={key.id}>
                  <TableCell className={classes.typeCell}>
                    <code className={classes.keyType}>{key.type}</code> (
                    {key.bits} bits)
                  </TableCell>
                  <TableCell className={classes.fingerprintCell}>
                    {key.fingerprint}
                  </TableCell>
                  <TableCell className={classes.titleCell}>
                    {key.comment}
                  </TableCell>
                  <TableCell size="small" align="right">
                    <IconButton onClick={() => setSelectedKey(key)}>
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Confirm
            open={selectedKey !== null}
            onClose={() => setSelectedKey(null)}
            title="Delete this SSH key?"
            text="You will no longer be able to access Critic's repositories using this key."
            accept={{
              label: "Delete",
              callback: () => dispatch(deleteSSHKey(selectedKey!.id)),
            }}
          />
        </>
      )}
    </Section>
  )
}

export default Registry.add("Settings.Account.SSHKeys", AccountSSHKeys)
