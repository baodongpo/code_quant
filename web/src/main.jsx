import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { initAuth } from './utils/auth.js'

// 初始化鉴权：从 URL ?token= 读取并存入 localStorage，清理 URL
initAuth()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
