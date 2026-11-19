import React, { useEffect, useState } from 'react';
import { Grid, Skeleton } from '@mui/material';
import { People, CheckCircle, VerifiedUser, CorporateFare } from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../../../store/hooks';
import { fetchTeamUsers } from '../../../store/slices/userSlice';
import StatCard from '../../common/stats/StatCard';

interface StatItem {
	label: string;
	value: string | number;
	subtitle: string;
	icon: React.ReactElement;
	color: string;
}

export const OrgAdminStatsPanel: React.FC = () => {
	const dispatch = useAppDispatch();
	const org = useAppSelector((state) => state.auth.user?.organization);
	const [stats, setStats] = useState<StatItem[] | null>(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		let cancelled = false;

		const loadData = async () => {
			try {
				const usersRes = await dispatch(fetchTeamUsers({ page: 1, pageSize: 200 }))
					.unwrap()
					.catch(() => ({ items: [], total: 0 }));

				if (cancelled) return;

				const totalUsers = usersRes.items.length;
				const activeUsers = usersRes.items.filter((m) => m.is_active).length;
				const verifiedUsers = usersRes.items.filter((m) => m.is_verified).length;
				const seatLimit = org?.user_limit ?? (org as any)?.max_users ?? 100;

				setStats([
					{
						label: 'Total Users',
						value: totalUsers,
						subtitle: 'Registered in organization',
						icon: <People sx={{ fontSize: 24 }} />,
						color: '#6366f1',
					},
					{
						label: 'Active Users',
						value: activeUsers,
						subtitle: `${Math.round((activeUsers / Math.max(1, totalUsers)) * 100)}% active rate`,
						icon: <CheckCircle sx={{ fontSize: 24 }} />,
						color: '#10b981',
					},
					{
						label: 'Verified Users',
						value: verifiedUsers,
						subtitle: 'Email verified accounts',
						icon: <VerifiedUser sx={{ fontSize: 24 }} />,
						color: '#06b6d4',
					},
					{
						label: 'Seat Capacity',
						value: `${activeUsers} / ${seatLimit}`,
						subtitle: org?.name || 'Organization quota',
						icon: <CorporateFare sx={{ fontSize: 24 }} />,
						color: '#f59e0b',
					},
				]);
			} catch (err) {
				console.error(err);
			} finally {
				if (!cancelled) setLoading(false);
			}
		};

		loadData();
		return () => {
			cancelled = true;
		};
	}, [dispatch, org]);

	if (loading) {
		return (
			<Grid container spacing={2}>
				{[1, 2, 3, 4].map((n) => (
					<Grid key={n} size={{ xs: 12, sm: 6, md: 3 }}>
						<Skeleton variant="rounded" height={100} sx={{ borderRadius: '16px' }} />
					</Grid>
				))}
			</Grid>
		);
	}

	return (
		<Grid container spacing={2}>
			{(stats || []).map((stat) => (
				<Grid key={stat.label} size={{ xs: 12, sm: 6, md: 3 }}>
					<StatCard
						title={stat.label}
						value={stat.value}
						subtitle={stat.subtitle}
						icon={stat.icon}
						color={stat.color}
					/>
				</Grid>
			))}
		</Grid>
	);
};

export default OrgAdminStatsPanel;
