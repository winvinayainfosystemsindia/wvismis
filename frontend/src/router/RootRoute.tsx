import React from 'react';
import { Navigate } from './tanstackCompat';
import { useAppSelector } from '../store/hooks';
import { Spinner } from '../components/common/spinner';

/**
 * The root "/" route: redirects signed-out visitors to "/auth/login",
 * and sends already-authenticated users straight to their dashboard.
 */
const RootRoute: React.FC = () => {
	const { isAuthenticated, isInitialized, user } = useAppSelector((state) => state.auth);

	if (!isInitialized) {
		return <Spinner fullPage size={96} text="Initializing WVISMIS" />;
	}

	if (isAuthenticated) {
		const dashboardPath = user?.organization?.public_id
			? `/org/${user.organization.public_id}/dashboard`
			: '/dashboard';
		return <Navigate to={dashboardPath} replace />;
	}

	return <Navigate to="/auth/login" replace />;
};

export default RootRoute;
