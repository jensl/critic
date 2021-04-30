import React, { createContext, useContext } from "react"
import { assertNotNull } from "../debug"
import Extension from "../resources/extension"
import ExtensionInstallation from "../resources/extensioninstallation"
import ExtensionVersion from "../resources/extensionversion"

type Props = {
  extension: Extension | undefined
  installation?: ExtensionInstallation | undefined
  version?: ExtensionVersion | undefined
}

const ExtensionContext = createContext<Props | null>(null)

export const WithExtension: React.FunctionComponent<Props> = ({
  extension,
  installation,
  version,
  children,
}) =>
  extension ? (
    <ExtensionContext.Provider value={{ extension, installation, version }}>
      {children}
    </ExtensionContext.Provider>
  ) : null

const useExtensionContext = () => {
  const ctx = useContext(ExtensionContext)
  assertNotNull(ctx)
  return ctx
}

export const useExtension = () => {
  const extension = useExtensionContext().extension
  assertNotNull(extension)
  return extension
}
export const useExtensionInstallation = () => useExtensionContext().installation
export const useExtensionVersion = () => useExtensionContext().version

export const useOptionalExtension = () => {
  const ctx = useContext(ExtensionContext)
  return ctx?.extension ?? null
}
