const path = module.require("path")
const { merge } = module.require("webpack-merge")
const common = module.require("./webpack.common.js")
const HtmlWebpackPlugin = module.require("html-webpack-plugin")

const listen_host = process.env.LISTEN_HOST
const listen_port = process.env.LISTEN_PORT
const api_backend = process.env.CRITIC_API_BACKEND
const ws_backend = process.env.CRITIC_WS_BACKEND

module.exports = merge(common, {
  mode: "development",
  target: "web",
  devServer: {
    contentBase: path.resolve(__dirname, "dist"),
    hot: true,
    historyApiFallback: {
      disableDotRule: true,
    },
    proxy: {
      "/api": {
        target: api_backend || "http://localhost:8080",
      },
      "/ws": {
        target: ws_backend || "http://localhost:8080",
        ws: true,
      },
    },
    host: listen_host || "localhost",
    port: listen_port ? parseInt(listen_port, 10) : 3000,
  },
  devtool: "inline-source-map",
  plugins: [
    new HtmlWebpackPlugin({
      minify: {
        collapseWhitespace: true,
        preserveLineBreaks: true,
      },
      template: "./public/index.html",
    }),
    //new webpack.HotModuleReplacementPlugin(),
  ],
})
