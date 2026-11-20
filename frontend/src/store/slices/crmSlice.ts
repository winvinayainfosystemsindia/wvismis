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
	async (_payload: { entityType: string; entityIds: number[] } | undefined) => {
		return [] as Reminder[];
	}
);

export const fetchReminders = createAsyncThunk(
	'crm/fetchReminders',
	async (_payload: { entityType: string; entityId: number } | undefined) => {
		return [] as Reminder[];
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
			});
	},
});

export const { setOwners } = crmSlice.actions;
export default crmSlice.reducer;
