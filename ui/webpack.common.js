const path = module.require("path")

module.exports = {
  entry: {
    main: "./src/index.tsx",
  },
  output: {
    path: path.resolve(__dirname, "dist"),
    filename: "static/js/[name]-[contenthash].bundle.js",
    publicPath: "/",
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        exclude: /node_modules/,
        use: [
          {
            loader: "ts-loader",
          },
        ],
      },
      /*{
        test: /\.(css|scss)$/,
        use: ["style-loader", "css-loader", "sass-loader"],
      },
      {
        test: /\.(gif|png|jpe?g|webp|svg)$/,
        use: {
          loader: "url-loader",
          options: {
            limit: 2048, // Convert images < 2kb to base64 strings
            name: "assets/img/[hash]-[name].[ext]",
          },
        },
      },
      {
        test: /\.ttf$/,
        use: {
          loader: "file-loader",
          options: {
            name: "assets/fonts/[name].[ext]",
          },
        },
      },
      {
        // fixes https://github.com/graphql/graphql-js/issues/1272
        test: /\.mjs$/,
        include: /node_modules/,
        type: "javascript/auto",
      },*/
    ],
  },
  resolve: {
    extensions: [".tsx", ".ts", ".js"],
    symlinks: false,
  },
  plugins: [],
  optimization: {
    splitChunks: {
      chunks: "all",
      name: "vendor",
    },
  },
}
