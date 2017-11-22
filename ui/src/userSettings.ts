import { UserSetting } from "./utils/UserSetting"

const theme = new UserSetting("theme", "light")
const sidebar = { isVisible: new UserSetting("sidebar.isVisible", false) }

export default { theme, sidebar }
