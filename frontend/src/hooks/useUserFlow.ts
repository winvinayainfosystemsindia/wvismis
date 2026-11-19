import { useAppSelector } from '../store/hooks';

export type UserFlow = 'super_admin' | 'org_admin' | 'org_team' | 'individual';

/**
 * Which of the app's four dashboard experiences the current user belongs to.
 */
export const useUserFlow = (): UserFlow => {
	const { user } = useAppSelector((state) => state.auth);

	if (user?.is_superuser || user?.role === 'super_admin') return 'super_admin';
	if (user?.organization?.others?.account_type === 'individual') return 'individual';
	if (user?.role === 'admin' || user?.role === 'org_admin') return 'org_admin';
	return 'org_team';
};

export default useUserFlow;
