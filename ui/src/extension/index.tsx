import React, { useContext, useEffect, useState } from "react"

import { useDispatch } from "../store"
import { ItemList } from "../actions"
import { Dispatch } from "../state"
import { assertNotNull } from "../debug"
import { useResource } from "../utils"
import Extension from "../resources/extension"
import { WithExtension } from "../utils/ExtensionContext"

type BeforeOption = { before: string }
type AfterOption = { after: string }
type Options = BeforeOption | AfterOption | {}

type FetchOptions = {
  method?: "GET" | "PATCH" | "POST" | "PUT" | "DELETE"
  path?: string
  headers?: { [name: string]: string }
  body?: string
  json?: any
}

export class Critic {
  constructor(readonly dispatch: Dispatch, readonly extension: Extension) {}

  registerItem(
    list: ItemList,
    itemID: string,
    render: React.FunctionComponent<{}>,
    options: Options = {},
  ) {
    this.dispatch({
      type: "ADD_ITEM_TO_LIST",
      list,
      extensionID: this.extension.id,
      itemID,
      render,
      before: "before" in options ? options.before : null,
      after: "after" in options ? options.after : null,
    })
  }

  fetch(
    endpoint: string,
    { method = "GET", path = "", headers = {}, body, json }: FetchOptions = {},
  ) {
    if (json !== undefined) {
      headers["content-type"] = "application/json"
      body = JSON.stringify(json)
    }
    return fetch(`/api/x/${this.extension.name}/endpoint/${endpoint}/${path}`, {
      method,
      headers,
      body,
      credentials: "same-origin",
    })
  }

  reset() {
    this.dispatch({ type: "RESET_EXTENSION", extensionID: this.extension.id })
  }
}

const CriticContext = React.createContext<Critic | null>(null)

type Props =
  | {
      extension: Extension
    }
  | {
      extensionKey: string
    }

export const WithCritic: React.FunctionComponent<Props> = ({
  children,
  ...props
}) => {
  const dispatch = useDispatch()
  const { byID, byKey } = useResource("extensions")

  const getExtension = () => {
    if ("extension" in props) return props.extension
    return byID.get(byKey.get(props.extensionKey) ?? -1)
  }

  const extension = getExtension()
  const [critic, setCritic] = useState<Critic | null>(null)

  useEffect(() => {
    if (extension) {
      const critic = new Critic(dispatch, extension)
      setCritic(critic)
      return () => critic.reset()
    }
    setCritic(null)
  }, [dispatch, extension])

  if (!critic) return null

  return (
    <CriticContext.Provider value={critic}>
      <WithExtension extension={extension}>{children}</WithExtension>
    </CriticContext.Provider>
  )
}

export const useCritic = () => {
  const critic = useContext(CriticContext)
  assertNotNull(critic)
  return critic
}
