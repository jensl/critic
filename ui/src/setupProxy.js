const proxy = require("http-proxy-middleware")

module.exports = (app) => {
  const api_backend = process.env.CRITIC_API_BACKEND
  if (typeof api_backend === "string")
    app.use(proxy("/api", { target: api_backend }))

  const ws_backend = process.env.CRITIC_WS_BACKEND
  if (typeof ws_backend === "string")
    app.use(proxy("/ws", { target: ws_backend, ws: true }))
}
