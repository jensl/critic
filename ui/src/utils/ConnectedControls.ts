import { useState } from "react"
import { any } from "."

export type SaveCallback = () => Promise<void>
export type SetSaveCallback = (
  key: string,
  callback: SaveCallback | null,
) => void
export type ConnectedControlProps = {
  setSave: SetSaveCallback
  resetCounter: number
}

type Controls = {
  [key: string]: SaveCallback | null
}

const useConnectedControls = () => {
  const [isSaving, setIsSaving] = useState(false)
  const [controls, setControls] = useState<Controls>({})
  const [resetCounter, setResetCounter] = useState(0)

  const isModified = any(
    Object.values(controls),
    (callback) => callback !== null,
  )

  const save = async () => {
    setIsSaving(true)
    try {
      for (const save of Object.values(controls))
        if (save !== null) await save()
    } finally {
      setIsSaving(false)
    }
  }
  const reset = () => setResetCounter((counter) => counter + 1)

  const setSave: SetSaveCallback = (key, callback) =>
    setControls((controls) => ({ ...controls, [key]: callback }))

  const connectedControlProps: ConnectedControlProps = { setSave, resetCounter }

  return {
    isModified,
    isSaving,
    save,
    reset,
    connectedControlProps,
  }
}

export default useConnectedControls
