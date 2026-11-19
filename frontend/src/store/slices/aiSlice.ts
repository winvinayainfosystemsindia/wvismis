import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit';
import aiService, { type AICreditBalance, type AIUsageSummary } from '../../services/aiService';

interface AIState {
	creditBalance: AICreditBalance | null;
	usageSummary: AIUsageSummary | null;
	loading: boolean;
	error: string | null;
	lastFetched: number | null;
}

const initialState: AIState = {
	creditBalance: null,
	usageSummary: null,
	loading: false,
	error: null,
	lastFetched: null,
};

export const fetchCreditBalance = createAsyncThunk(
	'ai/fetchCreditBalance',
	async (force: boolean = false, { getState, rejectWithValue }) => {
		const state = getState() as { ai: AIState };
		// If not forced and data is fresh (< 25s), don't refetch
		if (!force && state.ai.creditBalance && state.ai.lastFetched && Date.now() - state.ai.lastFetched < 25000) {
			return state.ai.creditBalance;
		}
		try {
			const res = await aiService.getCreditBalance();
			return res;
		} catch (err: any) {
			return rejectWithValue(err?.response?.data?.detail || err?.message || 'Failed to fetch AI credit balance');
		}
	}
);

export const fetchUsageSummary = createAsyncThunk(
	'ai/fetchUsageSummary',
	async (scope: 'mine' | 'organization' = 'mine', { rejectWithValue }) => {
		try {
			const res = await aiService.getUsageSummary(scope);
			return res;
		} catch (err: any) {
			return rejectWithValue(err?.response?.data?.detail || err?.message || 'Failed to fetch AI usage summary');
		}
	}
);

const aiSlice = createSlice({
	name: 'ai',
	initialState,
	reducers: {
		setCreditBalance: (state, action: PayloadAction<AICreditBalance>) => {
			state.creditBalance = action.payload;
			state.lastFetched = Date.now();
			state.loading = false;
			state.error = null;
		},
		setUsageSummary: (state, action: PayloadAction<AIUsageSummary>) => {
			state.usageSummary = action.payload;
		},
		decrementCredits: (state, action: PayloadAction<number>) => {
			if (state.creditBalance) {
				const newBalance = Math.max(0, state.creditBalance.balance - action.payload);
				state.creditBalance.balance = newBalance;
				if (state.creditBalance.granted > 0) {
					const used = Math.max(0, state.creditBalance.granted - newBalance);
					state.creditBalance.percent_used = Number(
						((used / state.creditBalance.granted) * 100).toFixed(1)
					);
				}
			}
		},
		clearAICache: (state) => {
			state.creditBalance = null;
			state.usageSummary = null;
			state.lastFetched = null;
		},
	},
	extraReducers: (builder) => {
		builder
			.addCase(fetchCreditBalance.pending, (state) => {
				if (!state.creditBalance) {
					state.loading = true;
				}
			})
			.addCase(fetchCreditBalance.fulfilled, (state, action) => {
				state.loading = false;
				state.creditBalance = action.payload;
				state.lastFetched = Date.now();
				state.error = null;
			})
			.addCase(fetchCreditBalance.rejected, (state, action) => {
				state.loading = false;
				state.error = action.payload as string;
			})
			.addCase(fetchUsageSummary.fulfilled, (state, action) => {
				state.usageSummary = action.payload;
			});
	},
});

export const { setCreditBalance, setUsageSummary, decrementCredits, clearAICache } = aiSlice.actions;
export default aiSlice.reducer;
