import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom';
import { DashboardView } from './features/dashboard/containers/DashboardView';
import { ProvidersView } from './features/providers/containers/ProvidersView';
import { RoutingView } from './features/routing/containers/RoutingView';
import { SkillsView } from './features/skills/containers/SkillsView';
import { SettingsView } from './features/settings/containers/SettingsView';
import { AutopilotView } from './features/autopilot/containers/AutopilotView';
import { MemoryView } from './features/memory/containers/MemoryView';

const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/dashboard" replace />,
  },
  {
    path: "/dashboard",
    element: <DashboardView />,
  },
  {
    path: "/providers",
    element: <ProvidersView />,
  },
  {
    path: "/routing",
    element: <RoutingView />,
  },
  {
    path: "/skills",
    element: <SkillsView />,
  },
  {
    path: "/settings",
    element: <SettingsView />,
  },
  {
    path: "/autopilot",
    element: <AutopilotView />,
  },
  {
    path: "/memory",
    element: <MemoryView />,
  }
]);

function App() {
  return (
    <RouterProvider router={router} />
  );
}

export default App;
