import { useMemo } from 'react';
import type { ColumnDefinition } from '../../common/table';
import type { TeamMember } from '../../../models/user';

export const getRoleColor = (role: string): 'error' | 'warning' | 'info' | 'success' | 'secondary' | 'primary' => {
	switch (role.toLowerCase()) {
		case 'super_admin': return 'secondary';
		case 'admin':
		case 'org_admin':
		case 'owner': return 'primary';
		case 'manager':
		case 'project_coordinator': return 'warning';
		case 'member':
		default: return 'info';
	}
};

interface OrgUserTableConfigProps {
	isMobile: boolean;
	isMedium: boolean;
}

export const useOrgUserTableConfig = ({ isMobile, isMedium }: OrgUserTableConfigProps) => {
	const columns = useMemo((): ColumnDefinition<TeamMember>[] => [
		{ id: 'full_name', label: 'Name', sortable: false },
		{ id: 'email', label: 'Email', sortable: false },
		{ id: 'username', label: 'Username', sortable: false, hidden: isMedium },
		{ id: 'role', label: 'Role', sortable: false, hidden: isMobile },
		{ id: 'is_active', label: 'Status', sortable: false },
		{ id: 'is_verified', label: 'Access', sortable: false, hidden: isMobile },
	], [isMobile, isMedium]);

	return { columns };
};
