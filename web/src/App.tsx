import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { HomePage } from "@/routes/HomePage";
import { LoginPage } from "@/routes/LoginPage";
import { RegisterPage } from "@/routes/RegisterPage";
import { CatalogPage } from "@/routes/CatalogPage";
import { DashboardPage } from "@/routes/DashboardPage";
import { NewRentalRequestPage } from "@/routes/NewRentalRequestPage";
import { NewReturnRequestPage } from "@/routes/NewReturnRequestPage";
import { ManagerRentalRequestsPage } from "@/routes/ManagerRentalRequestsPage";
import { ManagerReturnRequestsPage } from "@/routes/ManagerReturnRequestsPage";
import { ManagerRentalsPage } from "@/routes/ManagerRentalsPage";
import { AdminUsersPage } from "@/routes/AdminUsersPage";

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/register",
    element: <RegisterPage />,
  },
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "catalog", element: <CatalogPage /> },
      { path: "me", element: <DashboardPage /> },
      { path: "requests/new", element: <NewRentalRequestPage /> },
      { path: "me/return-requests/new", element: <NewReturnRequestPage /> },
      { path: "manager/requests", element: <ManagerRentalRequestsPage /> },
      { path: "manager/return-requests", element: <ManagerReturnRequestsPage /> },
      { path: "manager/rentals", element: <ManagerRentalsPage /> },
      { path: "admin/users", element: <AdminUsersPage /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
