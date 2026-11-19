import React, { useEffect, useState } from 'react';
import { Dialog, Box, TextField, MenuItem, InputAdornment, Typography } from '@mui/material';
import { Person, Badge, MailOutline, AssignmentInd, SupervisedUserCircleOutlined } from '@mui/icons-material';
import { EnterpriseForm, type FormStep } from '../../common/form';
import { useAppDispatch, useAppSelector } from '../../../store/hooks';
import { updateTeamUser } from '../../../store/slices/userSlice';
import { USER_ROLES, ROLE_LABELS, ROLE_DESCRIPTIONS, type UserRole, type TeamMember } from '../../../models/user';

interface EditOrgUserDialogProps {
	open: boolean;
	user: TeamMember | null;
	onClose: () => void;
	onSuccess: (message: string) => void;
}

export const EditOrgUserDialog: React.FC<EditOrgUserDialogProps> = ({ open, user, onClose, onSuccess }) => {
	const dispatch = useAppDispatch();
	const { users } = useAppSelector((state) => state.users);

	const [formData, setFormData] = useState({
		username: '',
		email: '',
		full_name: '',
		role: 'member' as UserRole,
		reporting_manager_id: '' as number | '',
	});
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [usernameWarning, setUsernameWarning] = useState(false);

	useEffect(() => {
		if (open && user) {
			setFormData({
				username: user.username || '',
				email: user.email || '',
				full_name: user.full_name || '',
				role: user.role || 'member',
				reporting_manager_id: user.reporting_manager_id || '',
			});
			setError(null);
		}
	}, [open, user]);

	const handleUsernameChange = (value: string) => {
		const hasUpper = /[A-Z]/.test(value);
		setUsernameWarning(hasUpper);
		handleChange('username', value.toLowerCase());
	};

	const handleChange = (field: string, value: any) => {
		setFormData((prev) => ({ ...prev, [field]: value }));
		setError(null);
	};

	const handleSubmit = async () => {
		if (!user) return;
		if (!formData.username.trim() || !formData.email.trim() || !formData.full_name.trim()) {
			setError('All fields are required.');
			return;
		}
		if (!/^[a-z0-9_]+$/.test(formData.username)) {
			setError('Username must be lowercase letters, numbers, and underscores only.');
			return;
		}

		setLoading(true);
		setError(null);
		try {
			await dispatch(
				updateTeamUser({
					publicId: user.public_id,
					payload: {
						...formData,
						reporting_manager_id: formData.reporting_manager_id || null,
					},
				})
			).unwrap();
			onSuccess('User details updated successfully.');
			onClose();
		} catch (err: any) {
			setError(typeof err === 'string' ? err : 'Failed to update user.');
		} finally {
			setLoading(false);
		}
	};

	const managerCandidates = users.filter((u) => u.is_active && u.id !== user?.id);

	const steps: FormStep[] = [
		{
			label: 'Edit Teammate Details',
			description: 'Update username, email, full name, role, or reporting manager',
			content: (
				<Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
					<TextField
						required
						fullWidth
						label="Full Name"
						placeholder="e.g. John Doe"
						value={formData.full_name}
						onChange={(e) => handleChange('full_name', e.target.value)}
						disabled={loading}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<Person sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							),
						}}
					/>
					<TextField
						required
						fullWidth
						label="Username"
						placeholder="e.g. john_doe"
						value={formData.username}
						onChange={(e) => handleUsernameChange(e.target.value)}
						disabled={loading}
						error={usernameWarning}
						helperText={
							usernameWarning
								? 'Uppercase converted to lowercase (only lowercase, numbers, and underscores allowed)'
								: 'Lowercase letters, numbers, and underscores only.'
						}
						FormHelperTextProps={{
							sx: {
								color: usernameWarning ? 'warning.main' : undefined,
							},
						}}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<Badge sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							),
						}}
					/>
					<TextField
						required
						fullWidth
						type="email"
						label="Email Address"
						placeholder="e.g. john.doe@example.com"
						value={formData.email}
						onChange={(e) => handleChange('email', e.target.value)}
						disabled={loading}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<MailOutline sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							),
						}}
					/>
					<TextField
						required
						select
						fullWidth
						label="Role"
						value={formData.role}
						onChange={(e) => handleChange('role', e.target.value)}
						disabled={loading}
						helperText={ROLE_DESCRIPTIONS[formData.role] || 'Select an organization access role'}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<AssignmentInd sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							),
						}}
					>
						{USER_ROLES.map((role) => (
							<MenuItem key={role} value={role}>
								<Box sx={{ py: 0.25 }}>
									<Typography variant="body2" sx={{ fontWeight: 600 }}>
										{ROLE_LABELS[role] || role}
									</Typography>
									<Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.72rem' }}>
										{ROLE_DESCRIPTIONS[role]}
									</Typography>
								</Box>
							</MenuItem>
						))}
					</TextField>
					<TextField
						select
						fullWidth
						label="Reporting Manager"
						value={formData.reporting_manager_id}
						onChange={(e) =>
							handleChange(
								'reporting_manager_id',
								e.target.value === '' ? '' : Number(e.target.value)
							)
						}
						disabled={loading}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<SupervisedUserCircleOutlined sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							),
						}}
					>
						<MenuItem value="">
							<em>None (Top-level)</em>
						</MenuItem>
						{managerCandidates.map((m) => (
							<MenuItem key={m.id} value={m.id}>
								{m.full_name || m.username} ({m.email})
							</MenuItem>
						))}
					</TextField>
				</Box>
			),
		},
	];

	return (
		<Dialog
			open={open}
			onClose={onClose}
			maxWidth="sm"
			fullWidth
			PaperProps={{ sx: { borderRadius: 0, boxShadow: 'none', bgcolor: 'transparent' } }}
		>
			<EnterpriseForm
				title="Edit Teammate"
				subtitle="Update member details in your organization"
				mode="edit"
				steps={steps}
				onSave={handleSubmit}
				onCancel={onClose}
				isSubmitting={loading}
				saveButtonText="Save Changes"
				error={error}
			/>
		</Dialog>
	);
};

export default EditOrgUserDialog;
