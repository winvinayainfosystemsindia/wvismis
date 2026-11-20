import dayjs from 'dayjs';
import type { Reminder } from '../models/crm/reminder';

export const formatReminderTime = (remindAt?: string): string => {
	if (!remindAt) return '';
	const dt = dayjs(remindAt);
	const today = dayjs().startOf('day');
	const target = dt.startOf('day');
	const diffDays = target.diff(today, 'day');

	if (diffDays === 0) return `Today at ${dt.format('h:mm A')}`;
	if (diffDays === 1) return `Tomorrow at ${dt.format('h:mm A')}`;
	if (diffDays === -1) return `Yesterday at ${dt.format('h:mm A')}`;
	return dt.format('MMM D, YYYY h:mm A');
};

export const getNextReminder = (reminders: Reminder[] = []): Reminder | null => {
	const pending = reminders.filter((r) => r.status === 'pending');
	if (pending.length === 0) return null;
	return pending.sort((a, b) => dayjs(a.remind_at).diff(dayjs(b.remind_at)))[0] || null;
};

export function isReminderOverdue(remindAt: string, status?: string): boolean {
	if (status && status !== 'pending') return false;
	return dayjs(remindAt).isBefore(dayjs());
}

export const getNextReminderByEntityId = (reminders: Reminder[] = []): Record<number, Reminder> => {
	const result: Record<number, Reminder> = {};
	for (const r of reminders) {
		if (r.status !== 'pending') continue;
		const existing = result[r.entity_id];
		if (!existing || dayjs(r.remind_at).isBefore(dayjs(existing.remind_at))) {
			result[r.entity_id] = r;
		}
	}
	return result;
};
