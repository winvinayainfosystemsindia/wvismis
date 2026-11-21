/* eslint-disable react-refresh/only-export-components */
import React from 'react';
import { Container, Typography, Button } from '@mui/material';
import {
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
	Outlet,
	type RouteComponent,
} from '@tanstack/react-router';
import { AuthProvider } from '../context/AuthContext';
import AuthInitializer from '../components/auth/AuthInitializer';
import Login, {
	Register,
	ForgotPassword,
	VerifyEmail,
	AcceptInvite,
	ResetPassword,
} from '../pages/auth';
import Dashboard from '../pages/dashboard';
import OrgManagement from '../pages/org/OrgManagement';
import { OrgConsole } from '../components/orgs';
import ProtectedRoute from './ProtectedRoute';
import RootRoute from './RootRoute';
import MainLayout from '../components/layout/MainLayout';
import SettingsLayout from '../components/layout/SettingsLayout';
import SuccessPage from '../pages/common/SuccessPage';
import NotFoundPage from '../pages/common/NotFoundPage';
import MaintenancePage from '../pages/common/MaintenancePage';
import PrivacyPolicyPage from '../pages/common/PrivacyPolicyPage';
import TermsPage from '../pages/common/TermsPage';
import CookiePolicyPage from '../pages/common/CookiePolicyPage';
import BillingSettings from '../pages/settings/BillingSettings';
import AICreditsUsagePage from '../pages/settings/AICreditsUsagePage';
import ProjectsListPage from '../pages/projects/ProjectsListPage';
import ProjectDetailPage from '../pages/projects/ProjectDetailPage';
import ProjectStatusPage from '../pages/projects/public/ProjectStatusPage';
import TimesheetPage from '../pages/timesheets/TimesheetPage';
import { Navigate, useLocation } from './tanstackCompat';

const LegacyAuthRedirect: React.FC<{ to: string }> = ({ to }) => {
	const location = useLocation();
	return <Navigate to={`${to}${location.search}`} replace />;
};

const RedirectTo: React.FC<{ to: string }> = ({ to }) => (
	<Navigate to={to} replace />
);

// ── 1. Root Route ───────────────────────────────────────────────────────────
const rootRoute = createRootRoute({
	component: () => (
		<AuthProvider>
			<AuthInitializer>
				<Outlet />
			</AuthInitializer>
		</AuthProvider>
	),
	notFoundComponent: NotFoundPage,
	errorComponent: ({ error }) => {
		console.error('Unhandled Route Error:', error);
		return (
			<Container maxWidth="md" sx={{ py: 8, textAlign: 'center' }}>
				<Typography variant="h4" color="error" gutterBottom sx={{ fontWeight: 700 }}>
					Something went wrong
				</Typography>
				<Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
					{error instanceof Error ? error.message : 'An unexpected error occurred.'}
				</Typography>
				<Button variant="contained" onClick={() => (window.location.href = '/')}>
					Reload Application
				</Button>
			</Container>
		);
	},
});

// ── 2. Public & Auth Routes ─────────────────────────────────────────────────
const indexRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/',
	component: RootRoute,
});

const authLoginRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/auth/login',
	component: Login,
});

const authRegisterRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/auth/register',
	component: Register,
});

const authForgotPasswordRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/auth/forgot-password',
	component: ForgotPassword,
});

const authVerifyEmailRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/auth/verify-email',
	component: VerifyEmail,
});

const authAcceptInviteRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/auth/accept-invite',
	component: AcceptInvite,
});

const authResetPasswordRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/auth/reset-password',
	component: ResetPassword,
});

// Legacy Auth Redirects
const legacyLoginRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/login',
	component: () => <LegacyAuthRedirect to="/auth/login" />,
});

const legacyRegisterRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/register',
	component: () => <LegacyAuthRedirect to="/auth/register" />,
});

const legacyForgotPasswordRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/forgot-password',
	component: () => <LegacyAuthRedirect to="/auth/forgot-password" />,
});

const legacyVerifyEmailRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/verify-email',
	component: () => <LegacyAuthRedirect to="/auth/verify-email" />,
});

const legacyAcceptInviteRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/accept-invite',
	component: () => <LegacyAuthRedirect to="/auth/accept-invite" />,
});

const legacyResetPasswordRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/reset-password',
	component: () => <LegacyAuthRedirect to="/auth/reset-password" />,
});

// Public Support & Legal Pages
const successRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/success',
	component: SuccessPage,
});

const maintenanceRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/maintenance',
	component: MaintenancePage,
});

const privacyPolicyRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/privacy-policy',
	component: PrivacyPolicyPage,
});

const termsRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/terms',
	component: TermsPage,
});

const cookiesRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/cookies',
	component: CookiePolicyPage,
});

// ── 3. Protected Layout & MainLayout Routes ─────────────────────────────────
const protectedLayoutRoute = createRoute({
	getParentRoute: () => rootRoute,
	id: 'protected',
	component: ProtectedRoute,
});

const mainLayoutRoute = createRoute({
	getParentRoute: () => protectedLayoutRoute,
	id: 'main-layout',
	component: MainLayout,
});

function createAppAndTenantRoutes(
	basePath: string,
	Component: RouteComponent
) {
	const standardRoute = createRoute({
		getParentRoute: () => mainLayoutRoute,
		path: basePath,
		component: Component,
	});
	const tenantRoute = createRoute({
		getParentRoute: () => mainLayoutRoute,
		path: `/org/$orgId${basePath}`,
		component: Component,
	});
	return [standardRoute, tenantRoute] as const;
}

const [dashboardRoute, orgDashboardRoute] = createAppAndTenantRoutes('/dashboard', Dashboard);
const [usersRoute, orgUsersRoute] = createAppAndTenantRoutes('/users', OrgManagement);
const organizationsRoute = createRoute({
	getParentRoute: () => mainLayoutRoute,
	path: '/organizations',
	component: OrgConsole,
});
const [billingRoute, orgBillingRoute] = createAppAndTenantRoutes('/billing', BillingSettings);
const [aiUsageRoute, orgAiUsageRoute] = createAppAndTenantRoutes('/ai-usage', AICreditsUsagePage);
const [projectsRoute, orgProjectsRoute] = createAppAndTenantRoutes('/projects', ProjectsListPage);
const [projectDetailRoute, orgProjectDetailRoute] = createAppAndTenantRoutes('/projects/$projectId', ProjectDetailPage);
const [timesheetsRoute, orgTimesheetsRoute] = createAppAndTenantRoutes('/timesheets', TimesheetPage);
const publicProjectStatusRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: '/projects/status/$token',
	component: ProjectStatusPage,
});
const [settingsRoute, orgSettingsRoute] = createAppAndTenantRoutes('/settings', SettingsLayout);
const [accountSettingsRoute, orgAccountSettingsRoute] = createAppAndTenantRoutes(
	'/account-settings',
	() => <RedirectTo to="/settings" />
);

// ── 4. Assemble TanStack Router Tree ────────────────────────────────────────
const routeTree = rootRoute.addChildren([
	indexRoute,
	authLoginRoute,
	authRegisterRoute,
	authForgotPasswordRoute,
	authVerifyEmailRoute,
	authAcceptInviteRoute,
	authResetPasswordRoute,
	legacyLoginRoute,
	legacyRegisterRoute,
	legacyForgotPasswordRoute,
	legacyVerifyEmailRoute,
	legacyAcceptInviteRoute,
	legacyResetPasswordRoute,
	successRoute,
	maintenanceRoute,
	privacyPolicyRoute,
	termsRoute,
	cookiesRoute,
	publicProjectStatusRoute,
	protectedLayoutRoute.addChildren([
		mainLayoutRoute.addChildren([
			dashboardRoute,
			orgDashboardRoute,
			usersRoute,
			orgUsersRoute,
			projectsRoute,
			orgProjectsRoute,
			projectDetailRoute,
			orgProjectDetailRoute,
			timesheetsRoute,
			orgTimesheetsRoute,
			organizationsRoute,
			billingRoute,
			orgBillingRoute,
			aiUsageRoute,
			orgAiUsageRoute,
			settingsRoute,
			orgSettingsRoute,
			accountSettingsRoute,
			orgAccountSettingsRoute,
		]),
	]),
]);

export const router = createRouter({
	routeTree,
	defaultPreload: 'intent',
	defaultNotFoundComponent: NotFoundPage,
});

declare module '@tanstack/react-router' {
	interface Register {
		router: typeof router;
	}
}

const AppRouter: React.FC = () => {
	return <RouterProvider router={router} />;
};

export default AppRouter;
