import { useResource, useSubscriptionIf } from "."
import { loadSystemSettingByKey, setSystemSetting } from "../actions/system"
import { assertNotReached } from "../debug"
import { useDispatch } from "../store"

export const useSystemSetting = <T>(
  key: string,
  check: (value: any) => T = (value) => value,
  load: boolean = false,
): [T | undefined, (newValue: T) => Promise<void>, string] => {
  const dispatch = useDispatch()

  const setting = useResource("systemsettings", ({ byID, byKey }) =>
    byID.get(byKey.get(key) || -1),
  )

  useSubscriptionIf(load, loadSystemSettingByKey, key)

  if (setting === undefined)
    return [undefined, async () => assertNotReached(), "N/A"]

  return [
    check(setting.value),
    async (newValue) =>
      void (await dispatch(setSystemSetting(setting, newValue))),
    setting.description,
  ]
}
