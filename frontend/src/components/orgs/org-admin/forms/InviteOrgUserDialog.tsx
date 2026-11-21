import React, { useEffect, useState } from 'react';
import { Dialog, Box, TextField, MenuItem, Typography, InputAdornment, Chip, IconButton } from '@mui/material';
import { Person, Badge, MailOutline, AssignmentInd, LockOutlined, Visibility, VisibilityOff } from '@mui/icons-material';
import { EnterpriseForm, type FormStep } from '../../../common/form';
import { useAppDispatch } from '../../../../store/hooks';
import { inviteTeamUser } from '../../../../store/slices/userSlice';
import { USER_ROLES, ROLE_LABELS, ROLE_DESCRIPTIONS, type UserRole } from '../../../../models/user';
import api from '../../../../services/api';

interface InviteOrgUserDialogProps {
	open: boolean;
	onClose: () => void;
	onSuccess: (message: string) => void;
}

const initialForm = {
	username: '',
	email: '',
	full_name: '',
	role: 'member' as UserRole,
	password: '',
	confirmPassword: '',
};

export const InviteOrgUserDialog: React.FC<InviteOrgUserDialogProps> = ({ open, onClose, onSuccess }) => {
	const dispatch = useAppDispatch();
	const [formData, setFormData] = useState(initialForm);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [usernameWarning, setUsernameWarning] = useState(false);
	const [showPassword, setShowPassword] = useState(false);
	const [showConfirmPassword, setShowConfirmPassword] = useState(false);

	const [usernameStatus, setUsernameStatus] = useState<'idle' | 'validating' | 'available' | 'error'>('idle');
	const [usernameMessage, setUsernameMessage] = useState('');
	const [usernameSuggestions, setUsernameSuggestions] = useState<string[]>([]);

	useEffect(() => {
		if (open) {
			setFormData(initialForm);
			setError(null);
			setUsernameStatus('idle');
			setUsernameMessage('');
			setUsernameSuggestions([]);
			setShowPassword(false);
			setShowConfirmPassword(false);
		}
	}, [open]);

	useEffect(() => {
		const trimmed = formData.username.trim().toLowerCase();
		if (!trimmed) {
			setUsernameStatus('idle');
			setUsernameMessage('');
			setUsernameSuggestions([]);
			return;
		}

		if (!/^[a-z0-9_]{3,30}$/.test(trimmed)) {
			setUsernameStatus('error');
			setUsernameMessage('Username must be 3-30 characters long (lowercase letters, numbers, underscores only).');
			setUsernameSuggestions([]);
			return;
		}

		setUsernameStatus('validating');
		const timer = setTimeout(async () => {
			try {
				const response = await api.get(`/onboard/check-username?username=${encodeURIComponent(trimmed)}`);
				if (response.data.available) {
					setUsernameStatus('available');
					setUsernameMessage('Username is available.');
					setUsernameSuggestions([]);
				} else {
					setUsernameStatus('error');
					setUsernameMessage(response.data.message || 'Username is taken.');
					setUsernameSuggestions(response.data.suggestions || []);
				}
			} catch (err: any) {
				setUsernameStatus('error');
				setUsernameMessage('Failed to verify username.');
				setUsernameSuggestions([]);
			}
		}, 400);

		return () => clearTimeout(timer);
	}, [formData.username]);

	const handleUsernameChange = (value: string) => {
		const hasUpper = /[A-Z]/.test(value);
		if (hasUpper) {
			setUsernameWarning(true);
		} else {
			setUsernameWarning(false);
		}
		handleChange('username', value.toLowerCase());
	};

	const handleChange = (field: keyof typeof initialForm, value: string) => {
		setFormData((prev) => {
			const updated = { ...prev, [field]: value };
			if (field === 'full_name') {
				const autoUsername = value
					.toLowerCase()
					.replace(/[^a-z0-9\s_]/g, '')
					.trim()
					.replace(/\s+/g, '_');
				
				const prevAutoUsername = prev.full_name
					.toLowerCase()
					.replace(/[^a-z0-9\s_]/g, '')
					.trim()
					.replace(/\s+/g, '_');
				
				if (!prev.username || prev.username === prevAutoUsername) {
					updated.username = autoUsername;
				}
			}
			return updated;
		});
		setError(null);
	};

	const handleSubmit = async () => {
		if (!formData.username.trim() || !formData.email.trim() || !formData.full_name.trim() || !formData.password) {
			setError('All fields including password are required.');
			return;
		}
		if (!/^[a-z0-9_]+$/.test(formData.username)) {
			setError('Username must be lowercase letters, numbers, and underscores only.');
			return;
		}
		if (formData.password.length < 8) {
			setError('Password must be at least 8 characters long.');
			return;
		}
		if (!/[A-Z]/.test(formData.password) || !/[a-z]/.test(formData.password) || !/[0-9]/.test(formData.password)) {
			setError('Password must contain at least one uppercase letter, one lowercase letter, and one number.');
			return;
		}
		if (formData.password !== formData.confirmPassword) {
			setError('Passwords do not match.');
			return;
		}

		setLoading(true);
		setError(null);
		try {
			await dispatch(inviteTeamUser({
				username: formData.username.trim().toLowerCase(),
				email: formData.email.trim().toLowerCase(),
				full_name: formData.full_name.trim(),
				role: formData.role,
				password: formData.password,
			})).unwrap();
			onSuccess(`Teammate ${formData.full_name || formData.username} created successfully with login credentials.`);
			onClose();
		} catch (err: any) {
			setError(typeof err === 'string' ? err : 'Failed to create teammate.');
		} finally {
			setLoading(false);
		}
	};

	const steps: FormStep[] = [
		{
			label: 'Teammate Information & Credentials',
			description: 'Create account and set initial password',
			content: (
				<Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.2 }}>
					<Typography variant="body2" color="text.secondary">
						Enter the teammate's details and set their login password. They can immediately log in with these credentials.
					</Typography>
					<TextField
						required fullWidth label="Full Name" placeholder="e.g. John Doe" value={formData.full_name}
						onChange={(e) => handleChange('full_name', e.target.value)} disabled={loading}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<Person sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							)
						}}
					/>
					<TextField
						required fullWidth label="Username" placeholder="e.g. john_doe"
						value={formData.username} onChange={(e) => handleUsernameChange(e.target.value)} disabled={loading}
						error={usernameStatus === 'error' || usernameWarning}
						helperText={
							usernameWarning 
								? "Uppercase converted to lowercase (only lowercase, numbers, and underscores allowed)" 
								: (usernameMessage || "Lowercase letters, numbers, and underscores only.")
						}
						FormHelperTextProps={{
							sx: {
								color: usernameWarning 
									? 'warning.main' 
									: (usernameStatus === 'available' ? 'success.main' : undefined)
							}
						}}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<Badge sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							)
						}}
					/>
					{usernameSuggestions.length > 0 && usernameStatus !== 'available' && (
						<Box sx={{ mt: -1.5, mb: 1, px: 1 }}>
							<Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.75, fontWeight: 600 }}>
								Username taken — try a suggestion:
							</Typography>
							<Box display="flex" flexWrap="wrap" gap={1}>
								{usernameSuggestions.map((sug) => (
									<Chip
										key={sug}
										label={sug}
										size="small"
										clickable
										onClick={() => { setFormData((prev) => ({ ...prev, username: sug })); setUsernameWarning(false); }}
										sx={{
											fontWeight: 700,
											fontSize: '0.75rem',
											bgcolor: 'rgba(139, 124, 246, 0.1)',
											color: 'primary.main',
											border: '1px solid rgba(139, 124, 246, 0.2)',
											'&:hover': {
												bgcolor: 'rgba(139, 124, 246, 0.2)',
											}
										}}
									/>
								))}
							</Box>
						</Box>
					)}
					<TextField
						required fullWidth type="email" label="Email Address" placeholder="e.g. john.doe@example.com" value={formData.email}
						onChange={(e) => handleChange('email', e.target.value)} disabled={loading}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<MailOutline sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							)
						}}
					/>
					<TextField
						required select fullWidth label="Role" value={formData.role}
						onChange={(e) => handleChange('role', e.target.value)} disabled={loading}
						helperText={ROLE_DESCRIPTIONS[formData.role] || 'Select an organization access role'}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<AssignmentInd sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							)
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
						required fullWidth
						label="Password"
						type={showPassword ? 'text' : 'password'}
						placeholder="••••••••"
						value={formData.password}
						onChange={(e) => handleChange('password', e.target.value)}
						disabled={loading}
						helperText="Min. 8 characters with at least one uppercase letter, one lowercase letter, and one number"
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<LockOutlined sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							),
							endAdornment: (
								<InputAdornment position="end">
									<IconButton
										size="small"
										onClick={() => setShowPassword((prev) => !prev)}
										edge="end"
										aria-label={showPassword ? "Hide password" : "Show password"}
									>
										{showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
									</IconButton>
								</InputAdornment>
							),
						}}
					/>

					<TextField
						required fullWidth
						label="Confirm Password"
						type={showConfirmPassword ? 'text' : 'password'}
						placeholder="••••••••"
						value={formData.confirmPassword}
						onChange={(e) => handleChange('confirmPassword', e.target.value)}
						disabled={loading}
						error={Boolean(formData.confirmPassword && formData.password !== formData.confirmPassword)}
						helperText={formData.confirmPassword && formData.password !== formData.confirmPassword ? "Passwords do not match" : undefined}
						InputProps={{
							startAdornment: (
								<InputAdornment position="start">
									<LockOutlined sx={{ color: 'text.secondary', fontSize: 18, mr: 0.5 }} />
								</InputAdornment>
							),
							endAdornment: (
								<InputAdornment position="end">
									<IconButton
										size="small"
										onClick={() => setShowConfirmPassword((prev) => !prev)}
										edge="end"
										aria-label={showConfirmPassword ? "Hide password" : "Show password"}
									>
										{showConfirmPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
									</IconButton>
								</InputAdornment>
							),
						}}
					/>
				</Box>
			),
		},
	];

	return (
		<Dialog
			open={open} onClose={onClose} maxWidth="sm" fullWidth
			PaperProps={{ sx: { borderRadius: 0, boxShadow: 'none', bgcolor: 'transparent' } }}
		>
			<EnterpriseForm
				title="Add Teammate" subtitle="Create a new user with credentials for your organization" mode="create"
				steps={steps} onSave={handleSubmit} onCancel={onClose} isSubmitting={loading}
				saveButtonText="Create Teammate" error={error}
			/>
		</Dialog>
	);
};

export default InviteOrgUserDialog;
