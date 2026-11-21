import {
	Home as HomeIcon,
	ManageAccounts as UserIcon,
	CorporateFare as OrgIcon,
	ViewKanban as ProjectsIcon,
	Person as ProfileIcon,
	Tune as PreferencesIcon,
	Shield as SecurityIcon,
	Notifications as NotificationsIcon,
	ArrowBack as BackIcon,
	PendingActions as TimesheetIcon,
} from '@mui/icons-material';
import type { SvgIconComponent } from '@mui/icons-material';

export interface NavigationItem {
	label?: string;
	path?: string;
	icon?: SvgIconComponent;
	roles?: string[];
	/** Gated on User.is_superuser rather than role */
	requiresSuperuser?: boolean;
	children?: NavigationItem[];
	divider?: boolean;
	hidden?: boolean;
	sectionId?: string;
	isSection?: boolean;
}

export const topNavigation: NavigationItem[] = [
	{
		label: 'Workspace',
		isSection: true,
		children: [
			{
				label: 'Home',
				path: '/dashboard',
				icon: HomeIcon,
				roles: ['super_admin', 'admin', 'org_admin', 'manager', 'member'],
			},
			{
				label: 'Team',
				path: '/users',
				icon: UserIcon,
				roles: ['super_admin', 'admin', 'org_admin'],
			},
			{
				label: 'Projects',
				path: '/projects',
				icon: ProjectsIcon,
				roles: ['super_admin', 'admin', 'org_admin', 'manager', 'member'],
			},
			{
				label: 'Timesheets',
				path: '/timesheets',
				icon: TimesheetIcon,
				roles: ['super_admin', 'admin', 'org_admin', 'manager', 'member'],
			},
			{
				label: 'Billing',
				path: '/billing',
				roles: ['super_admin', 'admin', 'org_admin'],
				hidden: true,
			},
		],
	},
	{
		label: 'Administration',
		isSection: true,
		requiresSuperuser: true,
		children: [
			{
				label: 'Organizations',
				path: '/organizations',
				icon: OrgIcon,
				requiresSuperuser: true,
				roles: ['super_admin'],
			},
		],
	},
];

export const bottomNavigation: NavigationItem[] = [];

export const settingsNavigation: NavigationItem[] = [
	{ label: 'Back to Dashboard', icon: BackIcon, path: '/dashboard', divider: true },
	{ label: 'Profile', icon: ProfileIcon, sectionId: 'settings-profile' },
	{ label: 'Preferences', icon: PreferencesIcon, sectionId: 'settings-preferences' },
	{ label: 'Security', icon: SecurityIcon, sectionId: 'settings-security' },
	{ label: 'Notifications', icon: NotificationsIcon, sectionId: 'settings-notifications' },
];

/**
 * Resolves a route's configuration dynamically from top and bottom navigation lists.
 * Handles tenant-prefixed routes (e.g., /org/:orgId/users -> /users) automatically.
 */
export const getRouteConfig = (pathname: string): NavigationItem | undefined => {
	let normalizedPath = pathname;
	const orgMatch = pathname.match(/^\/org\/[^/]+(\/.*)?$/);
	if (orgMatch) {
		normalizedPath = orgMatch[1] || '/';
	}

	const findItem = (items: NavigationItem[]): NavigationItem | undefined => {
		for (const item of items) {
			if (item.path === normalizedPath) return item;
			if (item.children) {
				const found = findItem(item.children);
				if (found) return found;
			}
		}
		return undefined;
	};

	return findItem(topNavigation) || findItem(bottomNavigation);
};
