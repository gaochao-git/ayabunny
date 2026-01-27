import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import basicSsl from '@vitejs/plugin-basic-ssl';
import { resolve } from 'path';
export default defineConfig({
    plugins: [vue(), basicSsl()],
    resolve: {
        alias: {
            '@': resolve(__dirname, 'src'),
        },
    },
    server: {
        port: 3300,
        host: true, // 监听所有网络接口，允许局域网访问
        // https 由 basicSsl 插件提供
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8888',
                changeOrigin: true,
                secure: false,
            },
            '/ws': {
                target: 'ws://127.0.0.1:8888',
                ws: true,
                changeOrigin: true,
                secure: false,
            },
        },
    },
    // 注意：Silero VAD 现在通过后端 WebSocket 服务运行，不再需要 ONNX Runtime
});
