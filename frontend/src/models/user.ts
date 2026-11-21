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

/** Selectable organization roles when adding/editing team members */
export const USER_ROLES: UserRole[] = [
	'admin',
	'manager',
	'member',
];

export const ROLE_LABELS: Record<string, string> = {
	super_admin: 'Super Admin',
	admin: 'Admin',
	manager: 'Manager',
	member: 'Member',
	org_admin: 'Admin',
	owner: 'Admin',
	viewer: 'Member',
	user: 'Member',
	developer: 'Member',
	project_coordinator: 'Manager',
};

export const ROLE_DESCRIPTIONS: Record<string, string> = {
	super_admin: 'Platform super administrator: global system control and cross-organization management.',
	admin: 'Organization administrator: complete control of the organization, team members, billing, and settings.',
	manager: 'Project & team operations: create and manage projects, tasks, and review team timesheets.',
	member: 'Team contributor: view and collaborate on assigned projects, update tasks, and submit timesheets.',
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
