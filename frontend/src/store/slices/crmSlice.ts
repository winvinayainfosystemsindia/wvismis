import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit';
import type { CRMOwnerOption } from '../../models/crm/owner';
import type { Reminder } from '../../models/crm/reminder';
import type { CRMCompanyOption } from '../../models/crm/company';
import api from '../../services/api';

interface CRMState {
	owners: CRMOwnerOption[];
	ownersLoading: boolean;
	companyOptions: CRMCompanyOption[];
	activeReminders: Reminder[];
	reminders: Reminder[];
	remindersLoading: boolean;
}

const initialState: CRMState = {
	owners: [],
	ownersLoading: false,
	companyOptions: [],
	activeReminders: [],
	reminders: [],
	remindersLoading: false,
};

export const searchCompanyOptions = createAsyncThunk(
	'crm/searchCompanyOptions',
	async (_query?: string) => [] as CRMCompanyOption[]
);

export const fetchOwners = createAsyncThunk('crm/fetchOwners', async () => {
	try {
		const res = await api.get('/users?page_size=100');
		const items = res.data?.data?.items || res.data?.items || [];
		return items.map((u: any) => ({
			id: u.id,
			full_name: u.full_name || u.username || u.email,
			email: u.email,
		}));
	} catch {
		return [];
	}
});

export const fetchActiveReminders = createAsyncThunk(
	'crm/fetchActiveReminders',
	async (payload: { entityType: string; entityIds: number[] } | undefined) => {
		if (!payload || !payload.entityIds?.length) return [] as Reminder[];
		try {
			const res = await api.get('/reminders', {
				params: {
					entity_type: payload.entityType,
					entity_ids: payload.entityIds.join(','),
					status: 'pending',
				},
			});
			return res.data as Reminder[];
		} catch {
			return [] as Reminder[];
		}
	}
);

export const fetchReminders = createAsyncThunk(
	'crm/fetchReminders',
	async (payload: { entityType: string; entityId: number } | undefined) => {
		if (!payload || !payload.entityId) return [] as Reminder[];
		try {
			const res = await api.get('/reminders', {
				params: {
					entity_type: payload.entityType,
					entity_id: payload.entityId,
					status: 'pending',
				},
			});
			return res.data as Reminder[];
		} catch {
			return [] as Reminder[];
		}
	}
);

export const createReminder = createAsyncThunk(
	'crm/createReminder',
	async (payload: {
		entity_type: string;
		entity_id: number;
		title: string;
		description?: string;
		remind_at: string;
		send_email?: boolean;
	}) => {
		const res = await api.post('/reminders', payload);
		return res.data as Reminder;
	}
);

export const deleteReminder = createAsyncThunk(
	'crm/deleteReminder',
	async (reminderId: number) => {
		await api.delete(`/reminders/${reminderId}`);
		return reminderId;
	}
);

export const dismissReminder = createAsyncThunk(
	'crm/dismissReminder',
	async (reminderId: number) => {
		const res = await api.patch(`/reminders/${reminderId}/dismiss`);
		return res.data as Reminder;
	}
);

const crmSlice = createSlice({
	name: 'crm',
	initialState,
	reducers: {
		setOwners: (state, action: PayloadAction<CRMOwnerOption[]>) => {
			state.owners = action.payload;
		},
	},
	extraReducers: (builder) => {
		builder
			.addCase(fetchOwners.pending, (state) => {
				state.ownersLoading = true;
			})
			.addCase(fetchOwners.fulfilled, (state, action) => {
				state.ownersLoading = false;
				state.owners = action.payload;
			})
			.addCase(fetchOwners.rejected, (state) => {
				state.ownersLoading = false;
			})
			.addCase(fetchActiveReminders.fulfilled, (state, action) => {
				state.activeReminders = action.payload;
			})
			.addCase(fetchReminders.fulfilled, (state, action) => {
				state.reminders = action.payload;
			})
			.addCase(createReminder.fulfilled, (state, action) => {
				const reminder = action.payload;
				state.reminders = [reminder, ...state.reminders.filter((r) => r.id !== reminder.id)];
				state.activeReminders = [reminder, ...state.activeReminders.filter((r) => r.id !== reminder.id)];
			})
			.addCase(deleteReminder.fulfilled, (state, action) => {
				const id = action.payload;
				state.reminders = state.reminders.filter((r) => r.id !== id);
				state.activeReminders = state.activeReminders.filter((r) => r.id !== id);
			})
			.addCase(dismissReminder.fulfilled, (state, action) => {
				const updated = action.payload;
				state.reminders = state.reminders.filter((r) => r.id !== updated.id);
				state.activeReminders = state.activeReminders.filter((r) => r.id !== updated.id);
			});
	},
});

export const { setOwners } = crmSlice.actions;
export default crmSlice.reducer;
