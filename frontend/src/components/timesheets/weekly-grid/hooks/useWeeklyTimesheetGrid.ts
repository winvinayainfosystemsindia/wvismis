import { useState, useMemo } from 'react';
import type { ProjectTimeLog, OrgHoliday, TimesheetWeekUnlockRequest, TimesheetStatus } from '../../../../models/timesheet';
import { computeWeekStatus } from '../../shared/weekStatus';

interface TimesheetRow {
	id: string; // unique row id
	type: 'project_task' | 'project_only' | 'general';
	projectId?: number;
	projectName?: string;
	taskId?: number;
	taskTitle?: string;
	categoryId?: number;
	categoryName?: string;
	billingType: 'billable' | 'non_billable';
	cells: Record<string, ProjectTimeLog | undefined>; // mapped by YYYY-MM-DD
	totalHours: number;
}

interface UseWeeklyTimesheetGridArgs {
	dates: Date[];
	logs: ProjectTimeLog[];
	holidays: OrgHoliday[];
	myUnlockRequests: TimesheetWeekUnlockRequest[];
	onRequestUnlock: (reason?: string, requestType?: 'unlock' | 'revoke') => void;
	isCurrentWeek: boolean;
}

export const useWeeklyTimesheetGrid = ({
	dates,
	logs,
	holidays,
	myUnlockRequests,
	onRequestUnlock,
	isCurrentWeek
}: UseWeeklyTimesheetGridArgs) => {
	const [requestDialogOpen, setRequestDialogOpen] = useState(false);
	const [requestDialogMode, setRequestDialogMode] = useState<'unlock' | 'revoke'>('unlock');
	const [requestReason, setRequestReason] = useState('');
	const [requestReasonError, setRequestReasonError] = useState<string | null>(null);

	// Format helper YYYY-MM-DD
	const getFormatDateStr = (d: Date): string => {
		const year = d.getFullYear();
		const month = String(d.getMonth() + 1).padStart(2, '0');
		const day = String(d.getDate()).padStart(2, '0');
		return `${year}-${month}-${day}`;
	};

	const { todayStr, previousWeekMondayStr } = useMemo(() => {
		const now = new Date();
		const day = now.getDay();
		const diff = now.getDate() - day + (day === 0 ? -6 : 1);
		const todayMon = new Date(now);
		todayMon.setDate(diff);
		todayMon.setHours(0, 0, 0, 0);
		const prevMon = new Date(todayMon);
		prevMon.setDate(todayMon.getDate() - 7);
		return {
			todayStr: getFormatDateStr(now),
			previousWeekMondayStr: getFormatDateStr(prevMon)
		};
	}, []);

	const dateStrings = useMemo(() => dates.map(getFormatDateStr), [dates]);

	// Map holidays by date string
	const holidayMap = useMemo(() => {
		const map: Record<string, OrgHoliday> = {};
		holidays.forEach((h) => {
			map[h.holiday_date] = h;
		});
		return map;
	}, [holidays]);

	// Sunday is always treated as a holiday
	const sundayDateStrings = useMemo(
		() => new Set(dates.filter((d) => d.getDay() === 0).map(getFormatDateStr)),
		[dates]
	);
	const isHolidayDate = (dateStr: string) => !!holidayMap[dateStr] || sundayDateStrings.has(dateStr);
	const holidayLabel = (dateStr: string) => holidayMap[dateStr]?.name || 'Sunday';

	// Group logs into rows
	const gridRows = useMemo(() => {
		const rowsMap: Record<string, TimesheetRow> = {};

		logs.forEach((log) => {
			let rowKey = '';
			let type: 'project_task' | 'project_only' | 'general' = 'general';
			
			if (log.project_id && log.task_id) {
				type = 'project_task';
				rowKey = `proj_${log.project_id}_task_${log.task_id}_${log.billing_type}`;
			} else if (log.project_id) {
				type = 'project_only';
				rowKey = `proj_${log.project_id}_only_${log.billing_type}`;
			} else if (log.category_id) {
				type = 'general';
				rowKey = `cat_${log.category_id}_${log.billing_type}`;
			} else {
				rowKey = `fallback_${log.id}`;
			}

			if (!rowsMap[rowKey]) {
				rowsMap[rowKey] = {
					id: rowKey,
					type,
					projectId: log.project_id,
					projectName: log.project?.name,
					taskId: log.task_id,
					taskTitle: log.task?.title,
					categoryId: log.category_id,
					categoryName: log.category?.name,
					billingType: log.billing_type,
					cells: {},
					totalHours: 0
				};
			}

			const logDateStr = log.log_date;
			rowsMap[rowKey].cells[logDateStr] = log;
			rowsMap[rowKey].totalHours += Number(log.hours);
		});

		return Object.values(rowsMap);
	}, [logs]);

	// Calculate totals per day
	const dayTotals = useMemo(() => {
		const totals: Record<string, number> = {};
		dateStrings.forEach((dateStr) => {
			totals[dateStr] = 0;
		});

		logs.forEach((log) => {
			const dStr = log.log_date;
			if (totals[dStr] !== undefined) {
				totals[dStr] += Number(log.hours);
			}
		});

		return totals;
	}, [logs, dateStrings]);

	// Weekly aggregate status
	const weeklyStatus: TimesheetStatus = useMemo(() => computeWeekStatus(logs), [logs]);

	const weekStartStr = dateStrings[0];
	// Current week and previous week (covering today, previous day, and previous week)
	// allow modifying submitted/draft/rejected entries without manager permission.
	const isFreeEditWeek = weekStartStr >= previousWeekMondayStr;

	const activeGrant = myUnlockRequests.find(
		(r) => r.week_start_date === weekStartStr && r.status === 'approved' && !r.consumed_at
	);
	const pendingRequest = myUnlockRequests.find(
		(r) => r.week_start_date === weekStartStr && r.status === 'pending'
	);
	const latestDenied = myUnlockRequests
		.filter((r) => r.week_start_date === weekStartStr && r.status === 'denied')
		.sort((a, b) => (b.resolved_at || '').localeCompare(a.resolved_at || ''))[0];

	const hasApprovedEntries = useMemo(() => logs.some((l) => l.status === 'approved'), [logs]);
	const hasSubmittedEntries = useMemo(() => logs.some((l) => l.status === 'submitted'), [logs]);
	const hasApprovedOrSubmitted = hasApprovedEntries || hasSubmittedEntries;
	const hasUnsubmittedEntries = logs.some((l) => l.status === 'draft' || l.status === 'rejected');

	// Per-day unsubmitted counts and status for daily submission UI
	const unsubmittedByDay = useMemo(() => {
		const map: Record<string, number> = {};
		dateStrings.forEach((d) => {
			map[d] = 0;
		});
		logs.forEach((l) => {
			if ((l.status === 'draft' || l.status === 'rejected') && map[l.log_date] !== undefined) {
				map[l.log_date] += 1;
			}
		});
		return map;
	}, [logs, dateStrings]);

	const dayStatusMap = useMemo(() => {
		const map: Record<string, TimesheetStatus | 'empty'> = {};
		dateStrings.forEach((d) => {
			const dayLogs = logs.filter((l) => l.log_date === d);
			if (dayLogs.length === 0) {
				map[d] = 'empty';
			} else if (dayLogs.some((l) => l.status === 'rejected')) {
				map[d] = 'rejected';
			} else if (dayLogs.some((l) => l.status === 'draft')) {
				map[d] = 'draft';
			} else if (dayLogs.some((l) => l.status === 'submitted')) {
				map[d] = 'submitted';
			} else {
				map[d] = 'approved';
			}
		});
		return map;
	}, [logs, dateStrings]);

	// A week is closed if it has received final weekly approval from the manager,
	// OR if it is older than the previous week, already submitted, and has no active revoke grant.
	const isWeekClosed =
		hasApprovedEntries || (hasSubmittedEntries && !isFreeEditWeek && !activeGrant);

	const grandTotal = Object.values(dayTotals).reduce((sum, h) => sum + h, 0);

	// Only weeks older than the previous week auto-lock when unsubmitted.
	const isLocked = !isCurrentWeek && !isFreeEditWeek && weeklyStatus === 'draft' && !activeGrant && !hasApprovedOrSubmitted;

	const handleOpenRequestDialog = (mode: 'unlock' | 'revoke' = 'unlock') => {
		setRequestDialogMode(mode);
		setRequestReason('');
		setRequestReasonError(null);
		setRequestDialogOpen(true);
	};

	const handleSubmitUnlockRequest = () => {
		if (requestDialogMode === 'revoke' && !requestReason.trim()) {
			setRequestReasonError('Please provide a reason for revoking the submitted timesheet.');
			return;
		}
		onRequestUnlock(requestReason.trim() || undefined, requestDialogMode);
		setRequestDialogOpen(false);
	};

	return {
		requestDialogOpen, setRequestDialogOpen,
		requestDialogMode,
		requestReason, setRequestReason,
		requestReasonError, setRequestReasonError,
		dateStrings,
		todayStr,
		isFreeEditWeek,
		holidayMap,
		sundayDateStrings,
		isHolidayDate,
		holidayLabel,
		gridRows,
		dayTotals,
		unsubmittedByDay,
		dayStatusMap,
		weeklyStatus,
		isWeekClosed,
		hasUnsubmittedEntries,
		hasApprovedEntries,
		hasSubmittedEntries,
		hasApprovedOrSubmitted,
		grandTotal,
		isLocked,
		pendingRequest,
		latestDenied,
		activeGrant,
		handleOpenRequestDialog,
		handleSubmitUnlockRequest
	};
};
