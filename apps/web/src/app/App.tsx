import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Toaster } from "@/components/toast";
import { Loading } from "@/components/ui";
import { useCatalog } from "@/lib/catalog";
import { useLiveData } from "@/lib/live";

// Code-split by route. The call desk loads speech recognition only when a call starts.
const Landing = lazy(() => import("@/features/landing/Landing"));
const PublicMenu = lazy(() => import("@/features/public-menu/PublicMenu"));
const CallDesk = lazy(() => import("@/features/call-desk/CallDesk"));
const Analytics = lazy(() => import("@/features/analytics/Analytics"));
const Upload = lazy(() => import("@/features/upload/Upload"));
const Combos = lazy(() => import("@/features/combos/Combos"));
const Orders = lazy(() => import("@/features/orders/OrdersPage"));
const Recordings = lazy(() => import("@/features/recordings/Recordings"));
const PricingLab = lazy(() => import("@/features/pricing-lab/PricingLab"));
const Settings = lazy(() => import("@/features/settings/SettingsPage"));

export function App() {
  const load = useCatalog((s) => s.load);
  const { pathname } = useLocation();
  useEffect(() => {
    void load();
  }, [load]);
  useLiveData();
  useEffect(() => window.scrollTo({ top: 0 }), [pathname]);
  return (
    <div className="min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-sm focus:bg-ink focus:px-3 focus:py-2 focus:text-plate">
        Skip to content
      </a>
      <Navbar />
      <main id="main">
        <Suspense fallback={<div className="px-6"><Loading /></div>}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/menu" element={<PublicMenu />} />
            <Route path="/desk" element={<CallDesk />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/combos" element={<Combos />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/orders/:id" element={<Orders />} />
            <Route path="/recordings" element={<Recordings />} />
            <Route path="/recordings/:id" element={<Recordings />} />
            <Route path="/pricing" element={<PricingLab />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
      <Toaster />
    </div>
  );
}
