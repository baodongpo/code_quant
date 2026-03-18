import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import StockAnalysis from './pages/StockAnalysis.jsx'
import WatchlistPage from './pages/WatchlistPage.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"           element={<StockAnalysis />} />
        <Route path="/watchlist"  element={<WatchlistPage />} />
        <Route path="*"           element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
