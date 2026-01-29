# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

语音助手 (Voice Chat Assistant) - A voice assistant application for children named "小智", built with Vue 3 + FastAPI + LangChain. Supports voice conversation, storytelling, poetry recitation, and music playback.

## Development Commands

### Backend (server/)
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r server/requirements.txt

# Run server (default port 8888)
cd server && python main.py

# Or use manage script from project root
./manage.sh start|stop|restart|status|logs
```

### Frontend (web/)
```bash
cd web
pnpm install
pnpm dev      # Dev server on port 3001
pnpm build    # Build to dist/
```

### Mobile (Capacitor)
```bash
cd web
npm run build
npx cap sync ios      # Sync to iOS
npx cap sync android  # Sync to Android
npx cap open ios      # Open in Xcode
npx cap open android  # Open in Android Studio
```

### Deployment
```bash
./release.sh web      # Build and deploy frontend
./release.sh server   # Deploy backend and restart
./release.sh all      # Deploy both
```

## Architecture

### Backend Structure (FastAPI + LangChain)
- `server/main.py` - FastAPI app entry, CORS config, static file serving
- `server/config.py` - Settings via pydantic-settings, loads from .env
- `server/api/` - API routes
  - `chat.py` - SSE streaming chat endpoint
  - `asr/` - ASR (Speech-to-Text) proxy/service
  - `tts/` - TTS (Text-to-Speech) proxy/service
  - `vad/` - Voice Activity Detection WebSocket
  - `skills.py` - Skills/stories CRUD API
  - `songs.py` - Music playback control
  - `video.py` - Video frame analysis
- `server/agent/` - LangChain Agent
  - `agent.py` - ReAct agent creation with tools, system prompt
  - `skills_loader.py` - Dynamic skill discovery and loading
  - `intent.py` - Intent detection
  - `tools/` - LangChain tools (tell_story, recite_poem, play_song, etc.)
- `server/skills/` - Skill data (storytelling/, poetry/, songs/, english/)

### Frontend Structure (Vue 3 + Composition API)
- `web/src/api/` - API client modules (chat, asr, tts, skills, songs, video)
- `web/src/composables/` - Reusable composition functions
  - `useChat.ts` - Chat state and message handling
  - `useTTSPlayer.ts` - TTS audio playback
  - `useMusicPlayer.ts` - Background music player
  - `useVAD.ts`, `useWebRTCVAD.ts`, `useSileroVAD.ts`, `useFunASRVAD.ts` - VAD implementations
  - `useVideoCapture.ts` - Camera video capture
  - `useAudioRecorder.ts` - Audio recording
- `web/src/components/` - Vue components
  - `ChatArea.vue` - Message display area
  - `Avatar3D.vue` - 3D avatar with Three.js
  - `RightPanel.vue` - Settings and skill management
  - `SettingsPanel.vue` - App settings
- `web/src/views/` - Page views
- `web/src/stores/` - Pinia state stores

### Key Patterns
- Agent uses LangGraph's `create_react_agent` with tool calling
- Skills are discovered at startup via `discover_skills()` and tools are registered dynamically
- Chat uses SSE streaming via `sse-starlette`
- VAD has multiple backends: webrtc (default), ten, silero_onnx
- Frontend API uses fetch with configurable base URL from env vars

### Environment Variables
Backend `server/.env`:
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` - LLM config
- `ASR_BASE_URL`, `ASR_MODEL` - Speech recognition
- `TTS_BASE_URL`, `TTS_MODEL`, `TTS_VOICE` - Text to speech
- `VAD_BACKEND` - VAD engine selection
- `PORT` - Server port (default 8888)

Frontend `web/.env`:
- `VITE_API_BASE_URL` - Backend API URL
- `VITE_WS_BASE_URL` - WebSocket URL
