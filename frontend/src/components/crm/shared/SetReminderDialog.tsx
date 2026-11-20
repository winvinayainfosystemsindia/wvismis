import React, { useState, useEffect } from 'react';
import {
	Dialog,
	DialogTitle,
	DialogContent,
	DialogActions,
	Button,
	Typography,
	Box,
	TextField,
	FormControlLabel,
	Switch,
	Chip,
	Stack,
	IconButton,
	CircularProgress,
	Alert,
	Divider,
} from '@mui/material';
import {
	NotificationsActiveOutlined,
	DeleteOutline,
	AccessTimeOutlined,
	EmailOutlined,
	Close as CloseIcon,
} from '@mui/icons-material';
import dayjs from 'dayjs';
import { useAppDispatch, useAppSelector } from '../../../store/hooks';
import type { Reminder } from '../../../models/crm/reminder';
import {
	fetchReminders,
	createReminder,
	deleteReminder,
} from '../../../store/slices/crmSlice';
import { formatReminderTime } from '../../../utils/reminders';

export interface SetReminderDialogProps {
	open: boolean;
	onClose: () => void;
	entityType?: string;
	entityId?: number;
	entityLabel?: string;
	defaultDueDate?: string;
	title?: string;
	onSaved?: () => void;
}

export const SetReminderDialog: React.FC<SetReminderDialogProps> = ({
	open,
	onClose,
	entityType = 'project_task',
	entityId,
	entityLabel,
	defaultDueDate,
	title,
	onSaved,
}) => {
	const dispatch = useAppDispatch();
	const reminders = useAppSelector((state) => state.crm.reminders);

	const [remindAt, setRemindAt] = useState<string>('');
	const [description, setDescription] = useState<string>('');
	const [sendEmail, setSendEmail] = useState<boolean>(true);
	const [isSaving, setIsSaving] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);

	// Find if an active reminder is already attached to this entity
	const activeReminder = entityId
		? reminders.find((r: Reminder) => r.entity_id === entityId && r.status === 'pending')
		: null;

	useEffect(() => {
		if (open && entityId) {
			dispatch(fetchReminders({ entityType, entityId }));
		}
	}, [open, entityId, entityType, dispatch]);

	useEffect(() => {
		if (open) {
			setError(null);
			setIsSaving(false);
			if (activeReminder) {
				setRemindAt(dayjs(activeReminder.remind_at).format('YYYY-MM-DDTHH:mm'));
				setDescription(activeReminder.description || '');
				setSendEmail(activeReminder.send_email ?? true);
			} else if (defaultDueDate) {
				// Default to 9:00 AM on due date or 1 day before
				const due = dayjs(defaultDueDate);
				const preset = due.subtract(1, 'day').hour(9).minute(0);
				if (preset.isAfter(dayjs())) {
					setRemindAt(preset.format('YYYY-MM-DDTHH:mm'));
				} else {
					setRemindAt(dayjs().add(1, 'hour').minute(0).format('YYYY-MM-DDTHH:mm'));
				}
			} else {
				setRemindAt(dayjs().add(1, 'hour').minute(0).format('YYYY-MM-DDTHH:mm'));
			}
		}
	}, [open, activeReminder, defaultDueDate]);

	const handlePresetClick = (presetType: '15m' | '1h' | 'tomorrow_9am' | 'due_day_before' | 'due_1h_before') => {
		const now = dayjs();
		if (presetType === '15m') {
			setRemindAt(now.add(15, 'minute').format('YYYY-MM-DDTHH:mm'));
		} else if (presetType === '1h') {
			setRemindAt(now.add(1, 'hour').format('YYYY-MM-DDTHH:mm'));
		} else if (presetType === 'tomorrow_9am') {
			setRemindAt(now.add(1, 'day').hour(9).minute(0).format('YYYY-MM-DDTHH:mm'));
		} else if (defaultDueDate && presetType === 'due_day_before') {
			setRemindAt(dayjs(defaultDueDate).subtract(1, 'day').hour(9).minute(0).format('YYYY-MM-DDTHH:mm'));
		} else if (defaultDueDate && presetType === 'due_1h_before') {
			setRemindAt(dayjs(defaultDueDate).subtract(1, 'hour').format('YYYY-MM-DDTHH:mm'));
		}
	};

	const handleDeleteReminder = async () => {
		if (!activeReminder) return;
		setIsSaving(true);
		try {
			await dispatch(deleteReminder(activeReminder.id)).unwrap();
			if (onSaved) onSaved();
			onClose();
		} catch (err: any) {
			setError(err?.message || 'Failed to remove reminder');
		} finally {
			setIsSaving(false);
		}
	};

	const handleSave = async () => {
		if (!entityId) {
			setError('No task selected to attach reminder');
			return;
		}
		if (!remindAt) {
			setError('Please select a reminder date and time');
			return;
		}

		const parsed = dayjs(remindAt);
		if (!parsed.isValid()) {
			setError('Invalid date/time format');
			return;
		}

		setIsSaving(true);
		setError(null);

		try {
			const taskTitle = title || entityLabel || 'Project Task';
			await dispatch(
				createReminder({
					entity_type: entityType,
					entity_id: entityId,
					title: `Reminder: ${taskTitle}`,
					description: description.trim() || undefined,
					remind_at: parsed.toISOString(),
					send_email: sendEmail,
				})
			).unwrap();

			if (onSaved) onSaved();
			onClose();
		} catch (err: any) {
			setError(err?.response?.data?.detail || err?.message || 'Failed to save reminder');
		} finally {
			setIsSaving(false);
		}
	};

	return (
		<Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
			<DialogTitle sx={{ m: 0, p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
				<Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
					<NotificationsActiveOutlined color="primary" />
					<Typography variant="h6" fontWeight={700}>
						Set Task Reminder
					</Typography>
				</Box>
				<IconButton size="small" onClick={onClose}>
					<CloseIcon fontSize="small" />
				</IconButton>
			</DialogTitle>

			<DialogContent dividers sx={{ p: 2.5 }}>
				{error && (
					<Alert severity="error" sx={{ mb: 2 }}>
						{error}
					</Alert>
				)}

				{/* Target Entity Context */}
				<Box sx={{ mb: 2.5, p: 1.5, bgcolor: 'action.hover', borderRadius: 1.5 }}>
					<Typography variant="caption" color="text.secondary" fontWeight={600} display="block" gutterBottom>
						REMINDER TARGET
					</Typography>
					<Typography variant="body1" fontWeight={700} color="text.primary">
						{entityLabel || title || 'Selected Project Task'}
					</Typography>
					{defaultDueDate && (
						<Typography variant="caption" color="error.main" fontWeight={600} sx={{ mt: 0.5, display: 'inline-block' }}>
							Due Date: {dayjs(defaultDueDate).format('MMM D, YYYY')}
						</Typography>
					)}
				</Box>

				{/* Existing Reminder Alert */}
				{activeReminder && (
					<Box
						sx={{
							mb: 2.5,
							p: 1.5,
							bgcolor: '#fff7ed',
							border: '1px solid #fed7aa',
							borderRadius: 1.5,
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'space-between',
						}}
					>
						<Box>
							<Typography variant="caption" sx={{ color: '#c2410c', fontWeight: 700 }}>
								CURRENT ACTIVE REMINDER
							</Typography>
							<Typography variant="body2" sx={{ color: '#9a3412', fontWeight: 600 }}>
								{formatReminderTime(activeReminder.remind_at)}
							</Typography>
						</Box>
						<Button
							size="small"
							color="error"
							variant="outlined"
							startIcon={<DeleteOutline fontSize="small" />}
							onClick={handleDeleteReminder}
							disabled={isSaving}
						>
							Remove
						</Button>
					</Box>
				)}

				{/* Quick Timing Presets */}
				<Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
					Quick Timing Presets
				</Typography>
				<Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2.5 }}>
					<Chip
						icon={<AccessTimeOutlined fontSize="small" />}
						label="In 15 mins"
						onClick={() => handlePresetClick('15m')}
						clickable
						size="small"
						variant="outlined"
					/>
					<Chip
						icon={<AccessTimeOutlined fontSize="small" />}
						label="In 1 hour"
						onClick={() => handlePresetClick('1h')}
						clickable
						size="small"
						variant="outlined"
					/>
					<Chip
						icon={<AccessTimeOutlined fontSize="small" />}
						label="Tomorrow at 9:00 AM"
						onClick={() => handlePresetClick('tomorrow_9am')}
						clickable
						size="small"
						variant="outlined"
					/>
					{defaultDueDate && (
						<>
							<Chip
								label="1 day before due (9 AM)"
								onClick={() => handlePresetClick('due_day_before')}
								clickable
								size="small"
								color="primary"
								variant="outlined"
							/>
							<Chip
								label="1 hour before due"
								onClick={() => handlePresetClick('due_1h_before')}
								clickable
								size="small"
								color="primary"
								variant="outlined"
							/>
						</>
					)}
				</Stack>

				{/* Scheduled Date/Time Input */}
				<TextField
					label="Remind At (Date & Time)"
					type="datetime-local"
					fullWidth
					value={remindAt}
					onChange={(e) => setRemindAt(e.target.value)}
					slotProps={{ inputLabel: { shrink: true } }}
					sx={{ mb: 2.5 }}
					helperText="Select the exact moment you wish to be alerted"
				/>

				{/* Description / Instructions */}
				<TextField
					label="Notes or Instructions (Optional)"
					multiline
					rows={2}
					fullWidth
					value={description}
					onChange={(e) => setDescription(e.target.value)}
					placeholder="e.g. Check client feedback or verify QA deployment"
					sx={{ mb: 2 }}
				/>

				<Divider sx={{ my: 1.5 }} />

				{/* Notification Channel Options */}
				<FormControlLabel
					control={
						<Switch
							checked={sendEmail}
							onChange={(e) => setSendEmail(e.target.checked)}
							color="primary"
						/>
					}
					label={
						<Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
							<EmailOutlined fontSize="small" color={sendEmail ? 'primary' : 'disabled'} />
							<Typography variant="body2" fontWeight={500}>
								Send Email Notification via WinVinaya Mail
							</Typography>
						</Box>
					}
				/>
				<Typography variant="caption" color="text.secondary" display="block" sx={{ ml: 4 }}>
					Dispatches a branded email alert with direct task access links to your registered email.
				</Typography>
			</DialogContent>

			<DialogActions sx={{ p: 2 }}>
				<Button onClick={onClose} disabled={isSaving} color="inherit">
					Cancel
				</Button>
				<Button
					onClick={handleSave}
					variant="contained"
					disabled={isSaving}
					startIcon={isSaving ? <CircularProgress size={16} color="inherit" /> : <NotificationsActiveOutlined />}
				>
					{isSaving ? 'Saving...' : activeReminder ? 'Update Reminder' : 'Set Reminder'}
				</Button>
			</DialogActions>
		</Dialog>
	);
};
