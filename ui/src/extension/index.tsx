import React, { useContext, useEffect, useState } from "react"

import { useDispatch } from "../store"
import { ADD_ITEM_TO_LIST, ItemList } from "../actions"
// import Extension from "../resources/extension"
import { Dispatch } from "../state"
import { assertNotNull } from "../debug"
import { useResource } from "../utils"
import { extension } from "../reducers/uiExtension"
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
      type: ADD_ITEM_TO_LIST,
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
    setCritic(extension ? new Critic(dispatch, extension) : null)
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
