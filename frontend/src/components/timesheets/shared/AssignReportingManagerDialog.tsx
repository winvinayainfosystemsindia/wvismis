import React, { useState, useEffect } from 'react';
import {
	Dialog,
	DialogTitle,
	DialogContent,
	DialogActions,
	Button,
	Typography,
	Box,
	Stack,
	FormControl,
	InputLabel,
	Select,
	MenuItem,
	CircularProgress,
	Alert,
	Chip,
	alpha,
	useTheme,
	Divider
} from '@mui/material';
import {
	SupervisorAccount as ManagerIcon,
	AccountTree as AllocationIcon
} from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../../../store/hooks';
import { fetchCurrentUser } from '../../../store/slices/authSlice';
import { fetchTeamUsers } from '../../../store/slices/userSlice';
import timesheetService from '../../../services/timesheetService';
import useToast from '../../../hooks/useToast';
import EnterpriseAvatar from '../../common/avatar/Avatar';

interface AvailableManager {
	id: number;
	public_id: string;
	email: string;
	username: string;
	full_name: string;
	role: string;
	direct_reports_count: number;
}

interface AssignReportingManagerDialogProps {
	open: boolean;
	onClose: () => void;
	targetUserId?: number | 'me';
	targetUserName?: string;
	currentManagerId?: number | null;
	onSuccess?: () => void;
	onOpenManagerAllocation?: () => void;
}

export const AssignReportingManagerDialog: React.FC<AssignReportingManagerDialogProps> = ({
	open,
	onClose,
	targetUserId = 'me',
	targetUserName,
	currentManagerId,
	onSuccess,
	onOpenManagerAllocation
}) => {
	const theme = useTheme();
	const dispatch = useAppDispatch();
	const toast = useToast();
	const currentUser = useAppSelector((state) => state.auth.user);

	const [managers, setManagers] = useState<AvailableManager[]>([]);
	const [loading, setLoading] = useState(false);
	const [submitting, setSubmitting] = useState(false);
	const [selectedManagerId, setSelectedManagerId] = useState<number | ''>(
		currentManagerId != null ? currentManagerId : ''
	);
	const [error, setError] = useState<string | null>(null);

	const isTargetSelf = targetUserId === 'me' || String(targetUserId) === String(currentUser?.id);
	const displayName = targetUserName || (isTargetSelf ? 'yourself' : 'team member');

	const isAdmin = Boolean(
		currentUser?.is_superuser ||
		currentUser?.role === 'admin' ||
		currentUser?.role === 'org_admin' ||
		currentUser?.role === 'super_admin' ||
		(currentUser?.role as string) === 'owner'
	);

	useEffect(() => {
		if (open) {
			setSelectedManagerId(currentManagerId != null ? currentManagerId : '');
			setError(null);
			fetchManagers();
		}
	}, [open, currentManagerId]);

	const fetchManagers = async () => {
		setLoading(true);
		setError(null);
		try {
			const data = await timesheetService.listAvailableManagers();
			setManagers(data);
		} catch (err: any) {
			setError(err?.response?.data?.detail || 'Failed to load eligible managers.');
		} finally {
			setLoading(false);
		}
	};

	const handleSave = async () => {
		setSubmitting(true);
		setError(null);
		try {
			const managerIdToSave = selectedManagerId === '' ? null : Number(selectedManagerId);
			const ref = targetUserId === 'me' ? 'me' : String(targetUserId);

			await timesheetService.assignReportingManager(ref, managerIdToSave);

			toast.success(
				managerIdToSave
					? `Reporting Manager assigned successfully.`
					: `Reporting Manager unassigned.`
			);

			// Refresh application auth user and team users
			await dispatch(fetchCurrentUser());
			dispatch(fetchTeamUsers({ page: 1, pageSize: 100 }));

			if (onSuccess) {
				onSuccess();
			}
			onClose();
		} catch (err: any) {
			const detail = err?.response?.data?.detail || err?.message || 'Failed to assign reporting manager.';
			setError(detail);
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<Dialog
			open={open}
			onClose={submitting ? undefined : onClose}
			maxWidth="sm"
			fullWidth
			PaperProps={{
				sx: {
					borderRadius: '16px',
					p: 1
				}
			}}
		>
			<DialogTitle sx={{ pb: 1 }}>
				<Stack direction="row" spacing={1.5} alignItems="center">
					<Box
						sx={{
							width: 40,
							height: 40,
							borderRadius: '10px',
							bgcolor: alpha(theme.palette.primary.main, 0.1),
							color: theme.palette.primary.main,
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center'
						}}
					>
						<ManagerIcon fontSize="medium" />
					</Box>
					<Box>
						<Typography variant="h6" fontWeight={700}>
							Assign Reporting Manager
						</Typography>
						<Typography variant="caption" color="text.secondary">
							Assign a manager to review and approve timesheet submissions for {displayName}.
						</Typography>
					</Box>
				</Stack>
			</DialogTitle>

			<Divider sx={{ my: 1 }} />

			<DialogContent sx={{ py: 2 }}>
				{error && (
					<Alert severity="error" sx={{ mb: 2.5, borderRadius: '10px' }}>
						{error}
					</Alert>
				)}

				{loading ? (
					<Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
						<CircularProgress size={32} />
					</Box>
				) : (
					<Stack spacing={2.5}>
						<FormControl fullWidth>
							<InputLabel id="assign-reporting-manager-label">Select Reporting Manager</InputLabel>
							<Select
								labelId="assign-reporting-manager-label"
								value={selectedManagerId}
								label="Select Reporting Manager"
								onChange={(e: any) => {
									const val = e.target.value;
									setSelectedManagerId(val === '' || val === null || val === undefined ? '' : Number(val));
								}}
							>
								<MenuItem value="">
									<em>None (Unassigned)</em>
								</MenuItem>
								{managers.map((m) => {
									const isSelf = isTargetSelf && m.id === Number(currentUser?.id);
									return (
										<MenuItem key={m.id} value={m.id}>
											<Stack direction="row" spacing={1.5} alignItems="center" sx={{ width: '100%', py: 0.5 }}>
												<EnterpriseAvatar
													name={m.full_name || m.username}
													size={28}
												/>
												<Box sx={{ flex: 1, minWidth: 0 }}>
													<Typography variant="body2" fontWeight={600} noWrap>
														{m.full_name || m.username} {isSelf && '(Self)'}
													</Typography>
													<Typography variant="caption" color="text.secondary" noWrap display="block">
														{m.email}
													</Typography>
												</Box>
												<Stack direction="row" spacing={1} alignItems="center">
													<Chip
														label={m.role.replace('_', ' ')}
														size="small"
														variant="outlined"
														sx={{ textTransform: 'capitalize', fontSize: '0.7rem', height: 20 }}
													/>
													<Chip
														label={`${m.direct_reports_count} reports`}
														size="small"
														color="primary"
														sx={{
															fontSize: '0.7rem',
															height: 20,
															bgcolor: alpha(theme.palette.primary.main, 0.08),
															color: theme.palette.primary.main,
															fontWeight: 600
														}}
													/>
												</Stack>
											</Stack>
										</MenuItem>
									);
								})}
							</Select>
						</FormControl>

						{isAdmin && onOpenManagerAllocation && (
							<Box
								sx={{
									p: 2,
									borderRadius: '12px',
									bgcolor: alpha(theme.palette.info.main, 0.06),
									border: `1px solid ${alpha(theme.palette.info.main, 0.15)}`,
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'space-between'
								}}
							>
								<Box>
									<Typography variant="subtitle2" fontWeight={700}>
										Need to organize your entire team?
									</Typography>
									<Typography variant="caption" color="text.secondary">
										Use the drag-and-drop hierarchy builder in the Manager Allocation tab.
									</Typography>
								</Box>
								<Button
									size="small"
									variant="outlined"
									color="info"
									startIcon={<AllocationIcon fontSize="small" />}
									onClick={() => {
										onClose();
										onOpenManagerAllocation();
									}}
									sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}
								>
									Open Allocation
								</Button>
							</Box>
						)}
					</Stack>
				)}
			</DialogContent>

			<DialogActions sx={{ px: 3, pb: 2 }}>
				<Button onClick={onClose} disabled={submitting} sx={{ borderRadius: '8px', textTransform: 'none' }}>
					Cancel
				</Button>
				<Button
					variant="contained"
					onClick={handleSave}
					disabled={loading || submitting}
					sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700, minWidth: 120 }}
				>
					{submitting ? <CircularProgress size={20} color="inherit" /> : 'Save Assignment'}
				</Button>
			</DialogActions>
		</Dialog>
	);
};

export default AssignReportingManagerDialog;
