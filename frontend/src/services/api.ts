import axios, { type InternalAxiosRequestConfig, type AxiosResponse } from 'axios';
import authService from './authService';

const api = axios.create({
	baseURL: `${import.meta.env.VITE_API_URL}/api/v1`,
	headers: {
		'Content-Type': 'application/json',
	},
});

// ── In-Memory Request Cache & Deduplication Layer ─────────────────────────────
interface CacheEntry {
	data: any;
	status: number;
	statusText: string;
	headers: any;
	expiresAt: number;
}

const apiCache = new Map<string, CacheEntry>();
const inFlightRequests = new Map<string, Promise<AxiosResponse<any>>>();

/**
 * Invalidate in-memory cached responses by pattern or clear all if no pattern provided.
 */
export const invalidateApiCache = (pattern?: string | RegExp): void => {
	if (!pattern) {
		apiCache.clear();
		return;
	}
	const regex = typeof pattern === 'string' ? new RegExp(pattern) : pattern;
	for (const key of apiCache.keys()) {
		if (regex.test(key)) {
			apiCache.delete(key);
		}
	}
};

// Wrap the default adapter to implement transparent deduplication & short-lived caching
const defaultAdapter = axios.getAdapter(axios.defaults.adapter);

api.defaults.adapter = async (config) => {
	const method = (config.method || 'get').toLowerCase();

	// Only cache & deduplicate safe, idempotent GET requests
	if (method !== 'get') {
		return defaultAdapter(config);
	}

	const noCache =
		config.headers?.['Cache-Control'] === 'no-cache' ||
		(config as any).noCache === true;
	const url = config.url || '';
	const paramsKey = config.params ? JSON.stringify(config.params) : '';
	const cacheKey = `${url}?${paramsKey}`;

	if (!noCache) {
		// 1. Check in-memory cache
		const cached = apiCache.get(cacheKey);
		if (cached && Date.now() < cached.expiresAt) {
			return {
				data: cached.data,
				status: cached.status,
				statusText: cached.statusText,
				headers: { ...cached.headers, 'x-cache': 'HIT' },
				config,
				request: {},
			} as AxiosResponse;
		}

		// 2. Coalesce in-flight duplicate requests (e.g., Navbar + Sidebar + Page)
		if (inFlightRequests.has(cacheKey)) {
			const inFlight = await inFlightRequests.get(cacheKey)!;
			return {
				data: inFlight.data,
				status: inFlight.status,
				statusText: inFlight.statusText,
				headers: { ...inFlight.headers, 'x-cache': 'INFLIGHT_COALESCED' },
				config,
				request: inFlight.request,
			} as AxiosResponse;
		}
	}

	// Dynamic TTL based on resource volatility
	let ttlMs = 15000; // 15 seconds default
	if (url.includes('/plans')) ttlMs = 300000; // 5 minutes (plans rarely change)
	else if (url.includes('/credits')) ttlMs = 25000; // 25 seconds
	else if (url.includes('/usage')) ttlMs = 25000;
	else if (url.includes('/auth/me')) ttlMs = 20000;
	else if (url.includes('/admin/stats')) ttlMs = 20000;

	const requestPromise = (async () => {
		try {
			const response = await defaultAdapter(config);
			if (!noCache && response.status >= 200 && response.status < 300) {
				apiCache.set(cacheKey, {
					data: response.data,
					status: response.status,
					statusText: response.statusText,
					headers: response.headers,
					expiresAt: Date.now() + ttlMs,
				});
			}
			return response;
		} finally {
			inFlightRequests.delete(cacheKey);
		}
	})();

	if (!noCache) {
		inFlightRequests.set(cacheKey, requestPromise);
	}

	return requestPromise;
};

// ── Token Refresh & Queue Logic ──────────────────────────────────────────────
let isRefreshing = false;
let failedQueue: Array<{
	resolve: (value?: any) => void;
	reject: (reason?: any) => void;
}> = [];

const processQueue = (error: any = null, token: string | null = null) => {
	failedQueue.forEach((promise) => {
		if (error) {
			promise.reject(error);
		} else {
			promise.resolve(token);
		}
	});

	failedQueue = [];
};

// Request interceptor for adding auth token
api.interceptors.request.use(
	(config: InternalAxiosRequestConfig) => {
		const token = authService.getAccessToken();
		if (token) {
			config.headers.Authorization = `Bearer ${token}`;
		}
		return config;
	},
	(error) => {
		return Promise.reject(error);
	}
);

const AUTH_ENDPOINTS_EXCLUDED_FROM_REFRESH = [
	'/auth/login',
	'/auth/refresh',
	'/auth/register',
	'/auth/accept-invite',
	'/auth/verify-email',
	'/auth/resend-verification',
	'/auth/forgot-password',
	'/auth/reset-password',
];

// Response interceptor for handling cache invalidation on mutations and token refresh
api.interceptors.response.use(
	(response) => {
		// Auto-invalidate related cache keys on successful mutations
		const method = (response.config.method || '').toLowerCase();
		if (['post', 'put', 'patch', 'delete'].includes(method)) {
			const url = response.config.url || '';
			if (url.includes('/credits')) {
				invalidateApiCache('/credits');
				invalidateApiCache('/usage');
			} else if (url.includes('/organization/plan') || url.includes('/plans')) {
				invalidateApiCache('/plans');
				invalidateApiCache('/auth/me');
				invalidateApiCache('/organization');
			} else if (url.includes('/auth/') || url.includes('/users/')) {
				invalidateApiCache('/auth/me');
				invalidateApiCache('/users');
			} else {
				invalidateApiCache();
			}
		}
		return response;
	},
	async (error) => {
		const originalRequest = error.config;
		const isExcludedFromRefresh = AUTH_ENDPOINTS_EXCLUDED_FROM_REFRESH.some((path) =>
			originalRequest?.url?.includes(path)
		);

		if (error.response?.status !== 401 || originalRequest._retry || isExcludedFromRefresh) {
			return Promise.reject(error);
		}

		if (isRefreshing) {
			return new Promise((resolve, reject) => {
				failedQueue.push({ resolve, reject });
			})
				.then((token) => {
					originalRequest.headers.Authorization = `Bearer ${token}`;
					return api(originalRequest);
				})
				.catch((err) => {
					return Promise.reject(err);
				});
		}

		originalRequest._retry = true;
		isRefreshing = true;

		try {
			const response = await authService.refreshToken();

			const publicPaths = [
				'/auth/',
				'/login',
				'/candidate-registration',
				'/success',
				'/maintenance',
				'/exam',
				'/meetings/manage',
				'/projects/status',
				'/book',
			];
			const isPublicPath = publicPaths.some((path) => window.location.pathname.startsWith(path));

			if (!response) {
				processQueue(new Error('Token refresh failed'), null);
				authService.clearTokens();

				if (!isPublicPath && window.location.pathname !== '/auth/login') {
					window.location.href = '/auth/login';
				}

				return Promise.reject(error);
			}

			const newToken = response.access_token;
			processQueue(null, newToken);

			originalRequest.headers.Authorization = `Bearer ${newToken}`;
			return api(originalRequest);
		} catch (refreshError) {
			processQueue(refreshError, null);
			authService.clearTokens();

			const publicPaths = [
				'/auth/',
				'/login',
				'/candidate-registration',
				'/success',
				'/maintenance',
				'/exam',
				'/candidate/interview',
				'/meetings/manage',
				'/projects/status',
				'/book',
			];
			const isPublicPath = publicPaths.some((path) => window.location.pathname.startsWith(path));

			if (!isPublicPath && window.location.pathname !== '/auth/login') {
				window.location.href = '/auth/login';
			}

			return Promise.reject(refreshError);
		} finally {
			isRefreshing = false;
		}
	}
);

export default api;
