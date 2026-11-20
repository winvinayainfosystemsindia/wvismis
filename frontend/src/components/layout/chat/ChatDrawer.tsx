import React from 'react';
import {
	TodayOutlined,
	GroupsOutlined,
	TrendingUpOutlined,
	AssessmentOutlined,
} from '@mui/icons-material';
import { IrisContextPanel } from '../../common/iris/IrisContextPanel';
import type { IrisQuickAction } from '../../common/iris/IrisChatBody';

interface ChatDrawerProps {
	open: boolean;
	onClose: () => void;
}

const GLOBAL_QUICK_ACTIONS: IrisQuickAction[] = [
	{ label: "My timesheet this week", icon: <TodayOutlined sx={{ fontSize: 15 }} />, message: "Show my timesheet summary and logged hours for this week." },
	{ label: 'Audit active projects', icon: <AssessmentOutlined sx={{ fontSize: 15 }} />, message: 'Run a health and risk analysis across all active projects.' },
	{ label: "Who's on leave today?", icon: <GroupsOutlined sx={{ fontSize: 15 }} />, message: "Who's on leave today?" },
	{ label: 'Show my open deals', icon: <TrendingUpOutlined sx={{ fontSize: 15 }} />, message: 'Show my open deals.' },
];

/** The global "AI co-worker" chat drawer, reachable from anywhere in the app -- a thin
 * wrapper around the shared IrisContextPanel (no contextModule, so its history is unfiltered
 * across every conversation, matching its role as the one always-available entry point). */
export const ChatDrawer: React.FC<ChatDrawerProps> = ({ open, onClose }) => (
	<IrisContextPanel open={open} onClose={onClose} subtitle="AI co-worker" quickActions={GLOBAL_QUICK_ACTIONS} />
);

export default ChatDrawer;
