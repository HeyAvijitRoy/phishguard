/* eslint-disable @typescript-eslint/no-var-requires */
const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const CopyWebpackPlugin = require("copy-webpack-plugin");
const devCerts = require("office-addin-dev-certs");

module.exports = async (env, argv) => {
  const httpsOptions = await devCerts.getHttpsServerOptions();

  return {
    entry: {
      taskpane: path.resolve(__dirname, "src/index.tsx")
    },
    output: {
      path: path.resolve(__dirname, "dist"),
      filename: "[name].[contenthash].js",
      clean: true
    },
    resolve: {
      extensions: [".ts", ".tsx", ".js"]
    },
    module: {
      rules: [
        {
          test: /\.tsx?$/,
          use: "ts-loader",
          exclude: /node_modules/
        },
        {
          test: /\.css$/,
          use: ["style-loader", "css-loader"]
        }
      ]
    },
    plugins: [
      new HtmlWebpackPlugin({
        filename: "taskpane.html",
        template: path.resolve(__dirname, "src/taskpane/taskpane.html"),
        chunks: ["taskpane"]
      }),
      new HtmlWebpackPlugin({
        filename: "support.html",
        template: path.resolve(__dirname, "src/support.html"),
        chunks: []
      }),
      new CopyWebpackPlugin({
        patterns: [
          {
            from: path.resolve(__dirname, "public"),
            to: "."
          },
          {
            from: path.resolve(__dirname, "assets"),
            to: "assets"
          },
          {
            from: path.resolve(__dirname, "node_modules/onnxruntime-web/dist/*.wasm"),
            to: "ort/[name][ext]"
          },
          {
            from: path.resolve(__dirname, "node_modules/onnxruntime-web/dist/*.mjs"),
            to: "ort/[name][ext]"
          },
          {
            from: path.resolve(__dirname, "node_modules/onnxruntime-web/dist/*.js"),
            to: "ort/[name][ext]"
          }
        ]
      })
    ],
    devServer: {
      port: 3000,
      server: {
        type: "https",
        options: httpsOptions
      },
      headers: {
        "Access-Control-Allow-Origin": "*"
      },
      static: [
        {
          directory: path.join(__dirname, "dist")
        },
        {
          directory: path.resolve(__dirname, "node_modules/onnxruntime-web/dist"),
          publicPath: "/ort"
        }
      ]
    }
  };
};
