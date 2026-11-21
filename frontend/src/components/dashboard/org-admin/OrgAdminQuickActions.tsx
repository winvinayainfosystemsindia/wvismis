import React from 'react';
import { Link as RouterLink } from '../../../router/tanstackCompat';
import { Card, CardContent, Typography, Box, useTheme, alpha, ButtonBase } from '@mui/material';
import { PersonAdd, ManageAccounts, Settings, Bolt, CorporateFare, Shield } from '@mui/icons-material';

interface QuickAction {
	label: string;
	description: string;
	icon: React.ReactElement;
	to: string;
	color: string;
}

const ACTIONS: QuickAction[] = [
	{
		label: 'Invite Member',
		description: 'Add new team member',
		icon: <PersonAdd sx={{ fontSize: 22 }} />,
		to: '/users',
		color: '#6366f1',
	},
	{
		label: 'Manage Team',
		description: 'View & edit users',
		icon: <ManageAccounts sx={{ fontSize: 22 }} />,
		to: '/users',
		color: '#06b6d4',
	},
	{
		label: 'AI Usage',
		description: 'Harness AI metrics',
		icon: <Bolt sx={{ fontSize: 22 }} />,
		to: '/ai-usage',
		color: '#10b981',
	},
	{
		label: 'Billing & Plan',
		description: 'Subscription tier',
		icon: <CorporateFare sx={{ fontSize: 22 }} />,
		to: '/billing',
		color: '#f59e0b',
	},
	{
		label: 'Security',
		description: 'Password & sessions',
		icon: <Shield sx={{ fontSize: 22 }} />,
		to: '/settings',
		color: '#8b5cf6',
	},
	{
		label: 'Settings',
		description: 'Workspace config',
		icon: <Settings sx={{ fontSize: 22 }} />,
		to: '/settings',
		color: '#64748b',
	},
];

export const OrgAdminQuickActions: React.FC = () => {
	const theme = useTheme();
	const isDark = theme.palette.mode === 'dark';
	const cardBg = theme.gradients.card;

	return (
		<Card
			sx={{
				borderRadius: '16px',
				border: `1px solid ${theme.palette.divider}`,
				boxShadow: isDark
					? '0 8px 32px 0 rgba(0, 0, 0, 0.2)'
					: '0 8px 32px 0 rgba(139, 124, 246, 0.04)',
				height: '100%',
				background: cardBg,
				backdropFilter: 'blur(20px)',
			}}
		>
			<CardContent sx={{ p: 2.5 }}>
				<Box display="flex" alignItems="center" gap={1.25} sx={{ mb: 2 }}>
					<Bolt color="primary" sx={{ fontSize: 20 }} />
					<Typography
						variant="subtitle2"
						sx={{
							fontWeight: 800,
							letterSpacing: '0.04em',
							textTransform: 'uppercase',
							fontSize: '0.78rem',
							color: 'text.primary',
						}}
					>
						Quick Actions
					</Typography>
				</Box>

				<Box
					sx={{
						display: 'grid',
						gridTemplateColumns: 'repeat(3, 1fr)',
						gap: 1.25,
					}}
				>
					{ACTIONS.map((action) => (
						<ButtonBase
							key={action.label}
							component={RouterLink}
							to={action.to}
							sx={{
								flexDirection: 'column',
								alignItems: 'center',
								gap: 1,
								p: 1.5,
								borderRadius: 2,
								border: `1px solid ${theme.palette.divider}`,
								bgcolor: isDark ? alpha('#fff', 0.02) : alpha(action.color, 0.03),
								transition: 'all 0.2s ease',
								textDecoration: 'none',
								'&:hover': {
									bgcolor: alpha(action.color, isDark ? 0.1 : 0.07),
									borderColor: alpha(action.color, 0.3),
									transform: 'translateY(-2px)',
									boxShadow: `0 4px 12px ${alpha(action.color, 0.15)}`,
								},
							}}
						>
							<Box
								sx={{
									width: 40,
									height: 40,
									borderRadius: 2,
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'center',
									bgcolor: alpha(action.color, isDark ? 0.15 : 0.1),
									color: action.color,
									mb: 0.25,
								}}
							>
								{action.icon}
							</Box>
							<Typography
								variant="caption"
								sx={{
									fontWeight: 700,
									color: 'text.primary',
									fontSize: '0.72rem',
									textAlign: 'center',
									lineHeight: 1.2,
								}}
							>
								{action.label}
							</Typography>
							<Typography
								variant="caption"
								sx={{
									color: 'text.secondary',
									fontSize: '0.62rem',
									textAlign: 'center',
									lineHeight: 1.2,
									display: { xs: 'none', sm: 'block' },
								}}
							>
								{action.description}
							</Typography>
						</ButtonBase>
					))}
				</Box>
			</CardContent>
		</Card>
	);
};

export default OrgAdminQuickActions;
