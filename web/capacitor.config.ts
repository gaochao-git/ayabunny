import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.ayabunny.xiaozhi',
  appName: '小智',
  webDir: 'dist',
  server: {
    // 允许 HTTP 连接（开发/测试用）
    cleartext: true,
    allowNavigation: ['*']
  },
  ios: {
    // 允许任意网络连接
    allowsLinkPreview: false
  }
};

export default config;
