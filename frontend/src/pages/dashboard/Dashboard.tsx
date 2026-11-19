import React from 'react';
import { Box, Grid } from '@mui/material';
import WelcomeHeader from '../../components/dashboard/WelcomeHeader';
import { PlatformPulsePanel } from '../../components/dashboard/super-admin/PlatformPulsePanel';
import { AttentionQueuePanel } from '../../components/dashboard/super-admin/AttentionQueuePanel';
import { PlatformKPIPanel } from '../../components/dashboard/super-admin/PlatformKPIPanel';
import { PlanDistributionPanel } from '../../components/dashboard/super-admin/PlanDistributionPanel';
import { RecentActivityPanel } from '../../components/dashboard/super-admin/RecentActivityPanel';
import { OrgSeatUsagePanel } from '../../components/dashboard/super-admin/OrgSeatUsagePanel';
import { SuperAdminQuickActions } from '../../components/dashboard/super-admin/SuperAdminQuickActions';
import { OrgAdminQuickActions } from '../../components/dashboard/org-admin/OrgAdminQuickActions';
import { OrgAdminStatsPanel } from '../../components/dashboard/org-admin/OrgAdminStatsPanel';
import { TeamRoleDistributionPanel } from '../../components/dashboard/org-admin/TeamRoleDistributionPanel';
import { AiUsageChartPanel } from '../../components/dashboard/org-admin/AiUsageChartPanel';
import { BillingHistoryPanel } from '../../components/dashboard/org-admin/BillingHistoryPanel';
import { useUserFlow } from '../../hooks/useUserFlow';

const Dashboard: React.FC = () => {
	const flow = useUserFlow();

	return (
		<Box component="main" sx={{ p: { xs: 1, sm: 0 }, display: 'flex', flexDirection: 'column', gap: 2 }}>
			<WelcomeHeader />

			{flow === 'super_admin' ? (
				<>
					{/* Row 1: KPI Cards */}
					<PlatformKPIPanel />

					{/* Row 2: Platform Pulse + Needs Attention + Quick Actions */}
					<Grid container spacing={2} alignItems="stretch">
						<Grid size={{ xs: 12, md: 3 }}>
							<PlatformPulsePanel />
						</Grid>
						<Grid size={{ xs: 12, md: 3.5 }}>
							<AttentionQueuePanel />
						</Grid>
						<Grid size={{ xs: 12, md: 5.5 }}>
							<SuperAdminQuickActions />
						</Grid>
					</Grid>

					{/* Row 3: Plan Distribution + Recent Registrations + Seat Usage Monitor */}
					<Grid container spacing={2} alignItems="stretch">
						<Grid size={{ xs: 12, md: 4 }}>
							<PlanDistributionPanel />
						</Grid>
						<Grid size={{ xs: 12, md: 4.5 }}>
							<RecentActivityPanel />
						</Grid>
						<Grid size={{ xs: 12, md: 3.5 }}>
							<OrgSeatUsagePanel />
						</Grid>
					</Grid>
				</>
			) : (
				<>
					{/* Row 1: KPI Stats Panel */}
					<OrgAdminStatsPanel />

					{/* Row 2: Team Role Distribution + AI Usage + Quick Actions */}
					<Grid container spacing={2} alignItems="stretch" sx={{ mt: 0.5 }}>
						<Grid size={{ xs: 12, md: 4 }}>
							<TeamRoleDistributionPanel />
						</Grid>
						<Grid size={{ xs: 12, md: 4 }}>
							<AiUsageChartPanel scope="organization" />
						</Grid>
						<Grid size={{ xs: 12, md: 4 }}>
							<OrgAdminQuickActions />
						</Grid>
					</Grid>

					{/* Row 3: Billing & Subscription Status */}
					<Grid container spacing={2} alignItems="stretch" sx={{ mt: 0.5 }}>
						<Grid size={{ xs: 12, md: 6 }}>
							<BillingHistoryPanel />
						</Grid>
					</Grid>
				</>
			)}
		</Box>
	);
};

export default Dashboard;
