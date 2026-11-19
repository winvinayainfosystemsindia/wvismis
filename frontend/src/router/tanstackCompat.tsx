/* eslint-disable react-refresh/only-export-components */
import React, { useCallback, useEffect, useMemo } from 'react';
import {
	Outlet,
	useRouter,
	useRouterState,
	useParams as useTanStackParams,
} from '@tanstack/react-router';

export { Outlet };

export interface NavigateOptions {
	replace?: boolean;
	state?: unknown;
}

export type NavigateFunction = {
	(to: string | number, options?: NavigateOptions): void;
	(options: {
		to: string;
		replace?: boolean;
		params?: Record<string, any>;
		search?: Record<string, any>;
	}): void;
};

function resolvePath(to: string, currentPathname: string): string {
	if (!to.startsWith('.')) {
		return to;
	}
	try {
		const base = currentPathname.endsWith('/') ? currentPathname : `${currentPathname}/`;
		const url = new URL(to, `http://localhost${base}`);
		return `${url.pathname}${url.search}${url.hash}`;
	} catch {
		return to;
	}
}

/**
 * TanStack Router powered `useNavigate` hook supporting both:
 * - `navigate('/path', { replace: true })`
 * - `navigate({ to: '/path', replace: true })`
 * - `navigate(-1)`
 */
export const useNavigate = (): NavigateFunction => {
	const router = useRouter();

	return useCallback(
		(
			toOrOptions:
				| string
				| number
				| {
						to: string;
						replace?: boolean;
						params?: Record<string, any>;
						search?: Record<string, any>;
				  },
			options?: NavigateOptions
		) => {
			if (typeof toOrOptions === 'number') {
				window.history.go(toOrOptions);
				return;
			}

			if (typeof toOrOptions === 'object' && toOrOptions !== null) {
				const target = resolvePath(toOrOptions.to, router.state.location.pathname);
				if (toOrOptions.replace) {
					router.history.replace(target);
				} else {
					router.history.push(target);
				}
				return;
			}

			const target = resolvePath(toOrOptions, router.state.location.pathname);
			if (options?.replace) {
				router.history.replace(target);
			} else {
				router.history.push(target);
			}
		},
		[router]
	) as NavigateFunction;
};

/**
 * TanStack Router powered `useLocation` hook returning normalized pathname & raw search string.
 */
export const useLocation = () => {
	const loc = useRouterState({ select: (s) => s.location });
	const rawSearch =
		typeof loc.searchStr === 'string'
			? loc.searchStr
			: typeof window !== 'undefined'
				? window.location.search
				: '';
	const search =
		rawSearch && !rawSearch.startsWith('?') ? `?${rawSearch}` : rawSearch;
	const rawHash = loc.hash || '';
	const hash = rawHash && !rawHash.startsWith('#') ? `#${rawHash}` : rawHash;

	return {
		pathname: loc.pathname,
		search,
		hash,
		state: (loc.state as any) ?? null,
		key: 'default',
	};
};

/**
 * TanStack Router powered `useParams` hook (non-strict so shared components work across routes).
 */
export const useParams = <
	T extends Record<string, string | undefined> = Record<string, string | undefined>,
>(): T => {
	return (useTanStackParams as any)({ strict: false }) as T;
};

/**
 * TanStack Router powered `useSearchParams` hook returning `[URLSearchParams, setSearchParams]`.
 */
export const useSearchParams = (): [
	URLSearchParams,
	(
		nextInit:
			| URLSearchParams
			| Record<string, string>
			| ((prev: URLSearchParams) => URLSearchParams | Record<string, string>),
		navigateOpts?: { replace?: boolean }
	) => void,
] => {
	const router = useRouter();
	const location = useLocation();

	const searchParams = useMemo(
		() => new URLSearchParams(location.search),
		[location.search]
	);

	const setSearchParams = useCallback(
		(
			nextInit:
				| URLSearchParams
				| Record<string, string>
				| ((prev: URLSearchParams) => URLSearchParams | Record<string, string>),
			navigateOpts?: { replace?: boolean }
		) => {
			const resolved =
				typeof nextInit === 'function' ? nextInit(new URLSearchParams(location.search)) : nextInit;
			const next =
				resolved instanceof URLSearchParams ? resolved : new URLSearchParams(resolved);
			const qs = next.toString();
			const nextUrl = `${location.pathname}${qs ? `?${qs}` : ''}${location.hash}`;
			if (navigateOpts?.replace) {
				router.history.replace(nextUrl);
			} else {
				router.history.push(nextUrl);
			}
		},
		[router, location.pathname, location.search, location.hash]
	);

	return [searchParams, setSearchParams];
};

export interface LinkProps
	extends Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> {
	to: string;
	replace?: boolean;
	state?: unknown;
}

/**
 * TanStack Router powered `Link` component compatible with MUI `component={RouterLink}`.
 */
export const Link = React.forwardRef<HTMLAnchorElement, LinkProps>(
	({ to, replace, onClick, children, ...rest }, ref) => {
		const navigate = useNavigate();

		const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
			if (onClick) onClick(e);
			if (
				!e.defaultPrevented &&
				e.button === 0 &&
				(!rest.target || rest.target === '_self') &&
				!(e.metaKey || e.altKey || e.ctrlKey || e.shiftKey)
			) {
				e.preventDefault();
				navigate(to, { replace });
			}
		};

		return (
			<a ref={ref} href={to} onClick={handleClick} {...rest}>
				{children}
			</a>
		);
	}
);
Link.displayName = 'TanStackRouterLink';

/**
 * TanStack Router powered declarative `<Navigate to="..." replace />` component.
 */
export const Navigate: React.FC<{
	to: string;
	replace?: boolean;
	state?: unknown;
}> = ({ to, replace = false }) => {
	const navigate = useNavigate();

	useEffect(() => {
		navigate(to, { replace });
	}, [to, replace, navigate]);

	return null;
};

/**
 * Pass-through Router wrapper for compatibility.
 */
export const BrowserRouter: React.FC<{ children: React.ReactNode }> = ({
	children,
}) => <>{children}</>;

export const Routes: React.FC<{ children?: React.ReactNode }> = ({
	children,
}) => <>{children}</>;

export const Route: React.FC<any> = () => null;
