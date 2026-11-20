import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography } from '@mui/material';

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

export const SetReminderDialog: React.FC<SetReminderDialogProps> = ({ open, onClose }) => {
	return (
		<Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
			<DialogTitle>Set Reminder</DialogTitle>
			<DialogContent>
				<Typography variant="body2" color="text.secondary">
					Reminders will be saved with this task schedule.
				</Typography>
			</DialogContent>
			<DialogActions>
				<Button onClick={onClose}>Close</Button>
			</DialogActions>
		</Dialog>
	);
};
