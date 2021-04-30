import React, { useContext } from "react"

const PrefixContext = React.createContext("")

export const usePrefix = () => useContext(PrefixContext)

const SetPrefix: React.FunctionComponent<{ prefix: string }> = ({
  prefix,
  children,
}) => <PrefixContext.Provider value={prefix}>{children}</PrefixContext.Provider>

export const AppendPrefix: React.FunctionComponent<{ append: string }> = ({
  append,
  children,
}) => {
  const prefix = usePrefix()
  console.log({ prefix })
  return (
    <PrefixContext.Provider value={`${prefix}/${append}`}>
      {children}
    </PrefixContext.Provider>
  )
}

export default SetPrefix
