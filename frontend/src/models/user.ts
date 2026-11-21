export type UserRole =
	| 'admin'
	| 'member'
	| 'viewer'
	| 'manager'
	| 'owner'
	| 'super_admin'
	| 'org_admin'
	| 'user'
	| 'developer'
	| 'sourcing'
	| 'placement'
	| 'trainer'
	| 'counselor'
	| 'project_coordinator'
	| 'marketing'
	| 'hr_admin'
	| 'hr_manager'
	| 'leadership';

/** Default selectable organization roles */
export const USER_ROLES: UserRole[] = [
	'admin',
	'member',
	'viewer',
	'manager',
	'owner',
];

export const ROLE_LABELS: Record<string, string> = {
	admin: 'Admin',
	member: 'Member',
	viewer: 'Viewer',
	manager: 'Manager',
	owner: 'Owner',
	user: 'Member',
	developer: 'Developer',
	super_admin: 'Super Admin',
	org_admin: 'Org Admin',
};

export const ROLE_DESCRIPTIONS: Record<string, string> = {
	admin: 'Full administration: invite users, configure modules, and manage workspace settings.',
	member: 'Standard member: collaborate on projects, run AI operations, and access shared data.',
	viewer: 'Read-only access: view projects, dashboards, and export reports without editing.',
	manager: 'Operations manager: assign work, oversee team members, and view activity reports.',
	owner: 'Organization owner: full billing, workspace governance, and account ownership.',
};

/** A row in the Org Admin's Team list — matches backend's UserListItem exactly. */
export interface TeamMember {
	id: number;
	public_id: string;
	username: string;
	email: string;
	full_name?: string;
	role: UserRole;
	is_active: boolean;
	is_verified: boolean;
	reporting_manager_id?: number | null;
	created_at: string;
}

/** Create or invite a teammate with credentials */
export interface InviteUserRequest {
	username: string;
	email: string;
	full_name: string;
	role: UserRole;
	password?: string;
}

export type CreateTeamUserRequest = InviteUserRequest;

export interface UpdateUserRequest {
	username?: string;
	email?: string;
	full_name?: string;
	role?: UserRole;
	reporting_manager_id?: number | null;
}
