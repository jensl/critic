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
            loader: "babel-loader",
            options: {
              presets: ["@babel/preset-typescript"],
            },
          },
        ],
      },
      {
        test: /\.md$/,
        type: "asset/source",
      },

      /*{
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
      //name: "vendor",

      name: (module, chunks, cacheGroupKey) => {
        if (chunks.length === 1) {
          if (chunks[0].name === "Markdown-Document-lazy")
            return "vendor-markdown-document"
          if (chunks[0].name === "Extension-Calls")
            return "vendor-extension-calls"
          if (chunks[0].name === "Tree-lazy") return "vendor-tree"
        }

        return "vendor-main"
      },

      cacheGroups: {
        default: false,
      },

      // cacheGroups: {
      //   dataGrid: {
      //     test: /[\\/]node_modules[\\/]@material-ui[\\/]data-grid[\\/]/,
      //     name: "data-grid",
      //     chunks: "all",
      //   },
      //   markdownIt: {
      //     test: /[\\/]node_modules[\\/](markdown-it|entities)[\\/]/,
      //     name: (module, chunks, cacheGroupKey) => {
      //       console.error("module", Object.keys(module))
      //       console.error("chunks", chunks)
      //       console.error("cacheGroupKey", cacheGroupKey)
      //       return "markdown-it"
      //     },
      //     chunks: "all",
      //   },
      // },
    },
  },
}
