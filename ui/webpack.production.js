const { merge } = module.require("webpack-merge")
const common = module.require("./webpack.common.js")
const { CleanWebpackPlugin } = require("clean-webpack-plugin")
const HtmlWebpackPlugin = module.require("html-webpack-plugin")
const TerserPlugin = module.require("terser-webpack-plugin")

module.exports = merge(common, {
  mode: "production",
  target: "browserslist",
  plugins: [
    new CleanWebpackPlugin(),
    new HtmlWebpackPlugin({
      minify: {
        collapseWhitespace: true,
        preserveLineBreaks: true,
      },
      template: "./public/index.html",
    }),
  ],
})
