import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { fetchCreditBalance } from '../store/slices/aiSlice';
import type { AICreditBalance } from '../services/aiService';

/**
 * Shared hook accessing the central Redux AI credit state.
 * Prevents redundant GET requests by caching balance across Navbar, Sidebar, and pages.
 * Instantly synchronized in real-time via WebSockets.
 */
export const useAICreditBalance = (): AICreditBalance | null => {
	const dispatch = useAppDispatch();
	const hasOrg = useAppSelector((state) => !!state.auth.user?.organization);
	const balance = useAppSelector((state) => state.ai.creditBalance);
	const lastFetched = useAppSelector((state) => state.ai.lastFetched);

	useEffect(() => {
		if (!hasOrg) return;

		// Only fetch if no balance in memory or cache is older than 25 seconds
		const isStale = !lastFetched || Date.now() - lastFetched > 25000;
		if (!balance || isStale) {
			dispatch(fetchCreditBalance(false));
		}
	}, [hasOrg, balance, lastFetched, dispatch]);

	return balance;
};

export default useAICreditBalance;
