var webpack = require('webpack');
var serverConfig = require('./configs/server');

var isDev = process.env.NODE_ENV == 'development';
var isProd = process.env.NODE_ENV == 'production';
var isTest = process.env.NODE_ENV == 'test';

definePlugin = new webpack.DefinePlugin({
  __DEV__: isDev,
  __TEST__: isTest,
  __PROD__: isProd,
  __DEBUG__: isDev
});

var config;
if (isProd) {
    console.log('[*] Prod config');
    config = require('./webpack.prod.config.js');
} else if (isTest) {
    console.log('[*] Test config');
    config = require('./webpack.test.config.js');
} else {
    console.log('[*] Dev config');
    config = require('./webpack.dev.config.js');
}

module.exports = config;
