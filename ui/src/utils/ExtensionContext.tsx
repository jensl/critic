import React, { createContext, useContext } from "react"
import { assertNotNull } from "../debug"
import Extension from "../resources/extension"

const ExtensionContext = createContext<Extension | undefined>(undefined)

type Props = {
  extension: Extension | undefined
}

export const WithExtension: React.FunctionComponent<Props> = ({
  extension,
  children,
}) =>
  extension ? (
    <ExtensionContext.Provider value={extension}>
      {children}
    </ExtensionContext.Provider>
  ) : null

export const useExtension = () => {
  const extension = useContext(ExtensionContext)
  assertNotNull(extension)
  return extension
}

export const useOptionalExtension = () => {
  const extension = useContext(ExtensionContext)
  return extension ?? null
}
