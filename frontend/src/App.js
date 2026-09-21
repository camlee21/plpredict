import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { restoreSavedCache, saveCacheAsItChanges } from "./api/persist";
import { FreshnessProvider, createQueryClient } from "./api/queries";
import "./App.css";
import Footer from "./components/Footer";
import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import FixturesPage from "./pages/FixturesPage";
import GameweekScorePage from "./pages/GameweekScorePage";
import HomePage from "./pages/HomePage";
import LeaguePage from "./pages/LeaguePage";
import LeaguePlayerGameweekPage from "./pages/LeaguePlayerGameweekPage";
import LeaguePlayerPage from "./pages/LeaguePlayerPage";
import LeaguesPage from "./pages/LeaguesPage";
import LoginPage from "./pages/LoginPage";
import PredictionsPage from "./pages/PredictionsPage";
import PrivacyPolicyPage from "./pages/PrivacyPolicyPage";
import ProfilePage from "./pages/ProfilePage";
import RegisterPage from "./pages/RegisterPage";

function App() {
  // One cache for the whole app, created once per mount (so tests each get
  // their own), and saved in the browser so reloads and new tabs start with
  // it. Anything restored is still re-checked by the usual refresh rules.
  const [queryClient] = useState(() => {
    const client = createQueryClient();
    restoreSavedCache(client);
    return client;
  });
  useEffect(() => saveCacheAsItChanges(queryClient), [queryClient]);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <FreshnessProvider>
          <BrowserRouter>
            <Navbar />
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/privacy" element={<PrivacyPolicyPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <HomePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/leagues"
                element={
                  <ProtectedRoute>
                    <LeaguesPage />
                  </ProtectedRoute>
                }
              />
              {/* Not wrapped in ProtectedRoute: a logged-out visitor (or a
                  logged-in non-member) following a league link should see the
                  page's own "members only" message rather than being bounced
                  straight to /login. */}
              <Route path="/leagues/:publicId" element={<LeaguePage />} />
              <Route
                path="/leagues/:publicId/players/:userId"
                element={
                  <ProtectedRoute>
                    <LeaguePlayerPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/leagues/:publicId/players/:userId/gameweek/:number"
                element={
                  <ProtectedRoute>
                    <LeaguePlayerGameweekPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/fixtures"
                element={
                  <ProtectedRoute>
                    <FixturesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/predict"
                element={
                  <ProtectedRoute>
                    <PredictionsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/scores/:number"
                element={
                  <ProtectedRoute>
                    <GameweekScorePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/profile"
                element={
                  <ProtectedRoute>
                    <ProfilePage />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            <Footer />
          </BrowserRouter>
        </FreshnessProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
