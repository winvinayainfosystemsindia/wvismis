import { configureStore } from '@reduxjs/toolkit';
import uiReducer from './slices/uiSlice';
import authReducer from './slices/authSlice';
import userReducer from './slices/userSlice';
import healthReducer from './slices/healthSlice';
import orgAdminReducer from './slices/orgAdminSlice';
import notificationsReducer from './slices/notificationSlice';
import aiReducer from './slices/aiSlice';
import projectsReducer from './slices/projectsSlice';
import crmReducer from './slices/crmSlice';

export const store = configureStore({
	reducer: {
		auth: authReducer,
		ui: uiReducer,
		users: userReducer,
		health: healthReducer,
		orgAdmin: orgAdminReducer,
		notifications: notificationsReducer,
		ai: aiReducer,
		projects: projectsReducer,
		crm: crmReducer,
	},
	middleware: (getDefaultMiddleware) =>
		getDefaultMiddleware({
			serializableCheck: false,
		}),
	devTools: import.meta.env.DEV && { maxAge: 25, trace: false },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
