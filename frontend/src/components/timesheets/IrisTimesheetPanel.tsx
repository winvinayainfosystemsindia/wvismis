import React from 'react';
import {
	TodayOutlined,
	CalendarViewWeekOutlined,
	TaskAltOutlined,
	AssignmentTurnedInOutlined,
	FactCheckOutlined,
} from '@mui/icons-material';
import { IrisContextPanel } from '../common/iris/IrisContextPanel';
import type { IrisQuickAction } from '../common/iris/IrisChatBody';

interface IrisTimesheetPanelProps {
	open: boolean;
	onClose: () => void;
	onActionConfirmed?: () => void;
}

const QUICK_ACTIONS: IrisQuickAction[] = [
	{ label: "Log today's hours", icon: <TodayOutlined sx={{ fontSize: 15 }} />, message: 'Log 4 hours for today with notes on my project tasks.' },
	{ label: 'Show my week', icon: <CalendarViewWeekOutlined sx={{ fontSize: 15 }} />, message: 'Show me what I logged this week, my progress against the weekly target, and missing days.' },
	{ label: 'Submit this week', icon: <TaskAltOutlined sx={{ fontSize: 15 }} />, message: "Submit this week's timesheet for final manager approval." },
	{ label: 'Pending team reviews', icon: <AssignmentTurnedInOutlined sx={{ fontSize: 15 }} />, message: 'Show all team timesheets and unlock requests awaiting my manager review.' },
	{ label: 'Compliance audit', icon: <FactCheckOutlined sx={{ fontSize: 15 }} />, message: 'Run a timesheet compliance audit for this week to find missing submissions.' },
];

/** Thin wrapper around the shared IrisContextPanel, scoped to this user's own "timesheet"
 * conversations (see AIChatSession.context_module) -- a real, persisted, multi-turn thread
 * supporting agentic logging, weekly submissions, manager approvals, and compliance audits. */
export const IrisTimesheetPanel: React.FC<IrisTimesheetPanelProps> = ({ open, onClose, onActionConfirmed }) => (
	<IrisContextPanel
		open={open}
		onClose={onClose}
		subtitle="Timesheet Agentic AI"
		contextModule="timesheet"
		quickActions={QUICK_ACTIONS}
		emptySubtitle="Ask me to log hours, audit your week, submit for approval, or review team timesheets."
		onActionCompleted={onActionConfirmed}
	/>
);

export default IrisTimesheetPanel;
