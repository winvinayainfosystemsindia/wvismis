import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
	Box,
	Drawer,
	Stack,
	Typography,
	IconButton,
	Button,
	Skeleton,
	Paper,
	useTheme,
	alpha,
	Collapse,
	Chip,
	Tooltip,
} from '@mui/material';
import {
	AutoAwesome,
	RefreshOutlined,
	CheckCircleOutlineRounded,
	WarningAmberRounded,
	ErrorOutlineRounded,
	ScheduleOutlined,
	TipsAndUpdatesOutlined,
	AccountTreeOutlined,
	DoneAllOutlined,
	ForumOutlined,
	PriorityHighOutlined,
	KeyboardArrowDownRounded,
	KeyboardArrowUpRounded,
} from '@mui/icons-material';
import projectService from '../../../../../services/projectService';
import type { ProjectTask, ProjectTaskUpdate, TaskInsight, TaskEstimate } from '../../../../../models/projects/projectTask';
import useToast from '../../../../../hooks/useToast';
import { IrisPanelHeader } from '../../../../common/iris/IrisPanelHeader';
import { IrisChatBody, type IrisQuickAction } from '../../../../common/iris/IrisChatBody';
import { useIrisChatPanel } from '../../../../common/iris/useIrisChatPanel';

interface IrisTaskPanelProps {
	open: boolean;
	onClose: () => void;
	task: ProjectTask;
	projectPublicId: string;
	onUpdateField: (fields: ProjectTaskUpdate) => Promise<void>;
}

const HEALTH_META: Record<string, { color: string; label: string; Icon: typeof CheckCircleOutlineRounded }> = {
	on_track: { color: '#2e7d32', label: 'On track', Icon: CheckCircleOutlineRounded },
	at_risk: { color: '#ed6c02', label: 'At risk', Icon: WarningAmberRounded },
	blocked: { color: '#d32f2f', label: 'Blocked', Icon: ErrorOutlineRounded },
};

const QUICK_ACTIONS: IrisQuickAction[] = [
	{ label: 'Break into subtasks', icon: <AccountTreeOutlined sx={{ fontSize: 15 }} />, message: 'Break this task down into a few clear, actionable subtasks.' },
	{ label: 'Mark subtasks done', icon: <DoneAllOutlined sx={{ fontSize: 15 }} />, message: 'Mark all subtasks on this task as completed.' },
	{ label: 'Summarize comments', icon: <ForumOutlined sx={{ fontSize: 15 }} />, message: 'Summarize the comment thread on this task.' },
	{ label: 'Bump to high priority', icon: <PriorityHighOutlined sx={{ fontSize: 15 }} />, message: 'Set the priority on this task to high.' },
];

export const IrisTaskPanel: React.FC<IrisTaskPanelProps> = ({ open, onClose, task, projectPublicId: _projectPublicId, onUpdateField }) => {
	const theme = useTheme();
	const toast = useToast();
	const brand = '#8B7CF6';

	const [insights, setInsights] = useState<TaskInsight | null>(null);
	const [insightsLoading, setInsightsLoading] = useState(false);
	const [insightsExpanded, setInsightsExpanded] = useState(true);

	const [estimate, setEstimate] = useState<TaskEstimate | null>(null);
	const [estimateLoading, setEstimateLoading] = useState(false);
	const [estimateExpanded, setEstimateExpanded] = useState(true);

	// Insights/estimate are cached per task (keyed by public_id)
	const insightsCache = useRef<Record<string, TaskInsight>>({});
	const estimateCache = useRef<Record<string, TaskEstimate>>({});

	const loadInsights = useCallback(async (taskPublicId: string, force = false) => {
		if (!force && insightsCache.current[taskPublicId]) {
			setInsights(insightsCache.current[taskPublicId]);
			setInsightsExpanded(true);
			return;
		}
		setInsightsLoading(true);
		setInsightsExpanded(true);
		try {
			const result = await projectService.getTaskInsights(taskPublicId);
			insightsCache.current[taskPublicId] = result;
			setInsights(result);
		} catch {
			setInsights(null);
			toast.error("Couldn't read this task right now.");
		} finally {
			setInsightsLoading(false);
		}
	}, [toast]);

	const loadEstimate = useCallback(async (taskPublicId: string, force = false) => {
		if (!force && estimateCache.current[taskPublicId]) {
			setEstimate(estimateCache.current[taskPublicId]);
			setEstimateExpanded(true);
			return;
		}
		setEstimateLoading(true);
		setEstimateExpanded(true);
		try {
			const result = await projectService.estimateTaskHours(taskPublicId);
			estimateCache.current[taskPublicId] = result;
			setEstimate(result);
		} catch {
			setEstimate(null);
			toast.error("Couldn't estimate this task right now.");
		} finally {
			setEstimateLoading(false);
		}
	}, [toast]);

	useEffect(() => {
		if (!open) return;
		setInsights(insightsCache.current[task.public_id] ?? null);
		setEstimate(estimateCache.current[task.public_id] ?? null);
	}, [open, task.public_id]);

	const handleApplyEstimate = async () => {
		if (estimate?.estimated_hours == null) return;
		await onUpdateField({ estimated_hours: estimate.estimated_hours });
		toast.success(`Estimate set to ${estimate.estimated_hours}h`);
	};

	const handleActionCompleted = useCallback(() => {
		loadInsights(task.public_id, true);
		loadEstimate(task.public_id, true);
	}, [task.public_id, loadInsights, loadEstimate]);

	const panel = useIrisChatPanel(open, 'project_task', task.public_id, handleActionCompleted);
	const { showSessions, setShowSessions, expanded, setExpanded, handleNewChat } = panel;

	const health = insights ? HEALTH_META[insights.health] : null;
	const HealthIcon = health?.Icon || CheckCircleOutlineRounded;

	const sectionCardSx = {
		p: 1.5,
		borderRadius: '12px',
		border: '1px solid',
		borderColor: 'divider',
		bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)',
		transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
		'&:hover': {
			borderColor: alpha(brand, 0.3),
		},
	} as const;

	return (
		<Drawer
			anchor="right"
			open={open}
			onClose={onClose}
			PaperProps={{
				sx: {
					width: { xs: '100%', sm: 460 },
					maxWidth: '100%',
					bgcolor: theme.palette.background.paper,
					color: theme.palette.text.primary,
					boxShadow: 'none',
				},
			}}
		>
			<Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
				{/* Header */}
				<IrisPanelHeader
					subtitle={task.title}
					onClose={onClose}
					showSessions={showSessions}
					onBack={() => setShowSessions(false)}
					onNewChat={handleNewChat}
					onShowHistory={() => setShowSessions(true)}
					expanded={expanded}
					onExpandToggle={() => setExpanded((v) => !v)}
				/>

				{/* Collapsible Overview Cards (Insights & Estimates) */}
				{!showSessions && (
					<Box
						sx={{
							p: 1.75,
							pb: 1,
							display: 'flex',
							flexDirection: 'column',
							gap: 1.25,
							maxHeight: { xs: '45vh', sm: '42vh' },
							overflowY: 'auto',
							flexShrink: 0,
							borderBottom: '1px solid',
							borderColor: 'divider',
							'&::-webkit-scrollbar': { width: '4px' },
							'&::-webkit-scrollbar-track': { bgcolor: 'transparent' },
							'&::-webkit-scrollbar-thumb': {
								bgcolor: alpha(theme.palette.text.primary, 0.12),
								borderRadius: '4px',
							},
						}}
					>
						{/* --- INSIGHTS / AT RISK CARD --- */}
						<Paper
							elevation={0}
							sx={{
								...sectionCardSx,
								borderColor: health ? alpha(health.color, 0.4) : 'divider',
							}}
						>
							{/* Card Header Row with Expand/Collapse */}
							<Stack
								direction="row"
								alignItems="center"
								justifyContent="space-between"
								onClick={() => setInsightsExpanded((prev) => !prev)}
								sx={{
									cursor: 'pointer',
									userSelect: 'none',
									py: 0.25,
								}}
							>
								<Stack direction="row" alignItems="center" spacing={1} sx={{ minWidth: 0 }}>
									<HealthIcon sx={{ fontSize: 18, color: health?.color || 'text.secondary', flexShrink: 0 }} />
									<Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.85rem' }}>
										{health?.label || 'Insights'}
									</Typography>
									{!insightsExpanded && insights && (
										<Chip
											size="small"
											label={
												insights.risk_reasons.length > 0
													? `${insights.risk_reasons.length} risk(s)`
													: 'Healthy'
											}
											sx={{
												height: 20,
												fontSize: '0.72rem',
												fontWeight: 700,
												bgcolor: health ? alpha(health.color, 0.12) : 'action.hover',
												color: health?.color || 'text.secondary',
											}}
										/>
									)}
								</Stack>

								<Stack direction="row" alignItems="center" spacing={0.5} onClick={(e) => e.stopPropagation()}>
									{insights && (
										<Tooltip title="Refresh health insights">
											<IconButton
												size="small"
												onClick={() => loadInsights(task.public_id, true)}
												disabled={insightsLoading}
												sx={{ p: 0.5 }}
											>
												<RefreshOutlined sx={{ fontSize: 15 }} />
											</IconButton>
										</Tooltip>
									)}
									<Tooltip title={insightsExpanded ? 'Collapse section' : 'Expand section'}>
										<IconButton
											size="small"
											onClick={() => setInsightsExpanded((prev) => !prev)}
											sx={{ p: 0.5 }}
										>
											{insightsExpanded ? (
												<KeyboardArrowUpRounded sx={{ fontSize: 18 }} />
											) : (
												<KeyboardArrowDownRounded sx={{ fontSize: 18 }} />
											)}
										</IconButton>
									</Tooltip>
								</Stack>
							</Stack>

							{/* Card Content Collapse */}
							<Collapse in={insightsExpanded} timeout="auto" unmountOnExit>
								<Box sx={{ mt: 1.25, pt: 1, borderTop: '1px dashed', borderColor: 'divider' }}>
									{insightsLoading ? (
										<Stack spacing={0.75}>
											<Skeleton variant="text" width="85%" height={16} />
											<Skeleton variant="text" width="65%" height={16} />
										</Stack>
									) : insights ? (
										insights.risk_reasons.length > 0 || insights.suggestions.length > 0 ? (
											<Stack
												spacing={0.85}
												sx={{
													maxHeight: 180,
													overflowY: 'auto',
													pr: 0.5,
													'&::-webkit-scrollbar': { width: '3px' },
													'&::-webkit-scrollbar-thumb': {
														bgcolor: alpha(theme.palette.text.primary, 0.15),
														borderRadius: '3px',
													},
												}}
											>
												{insights.risk_reasons.map((reason, i) => (
													<Stack key={`r-${i}`} direction="row" spacing={1} alignItems="flex-start">
														<Box
															sx={{
																width: 5,
																height: 5,
																borderRadius: '50%',
																bgcolor: health?.color || 'warning.main',
																mt: 0.8,
																flexShrink: 0,
															}}
														/>
														<Typography
															variant="body2"
															sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.45 }}
														>
															{reason}
														</Typography>
													</Stack>
												))}
												{insights.suggestions.map((s, i) => (
													<Stack
														key={`s-${i}`}
														direction="row"
														spacing={0.75}
														alignItems="flex-start"
														sx={{
															bgcolor: alpha(brand, 0.05),
															p: 0.75,
															borderRadius: '6px',
														}}
													>
														<TipsAndUpdatesOutlined sx={{ fontSize: 14, color: brand, mt: 0.2, flexShrink: 0 }} />
														<Typography
															variant="body2"
															sx={{ fontSize: '0.78rem', color: 'text.primary', lineHeight: 1.45 }}
														>
															{s}
														</Typography>
													</Stack>
												))}
											</Stack>
										) : (
											<Typography variant="body2" sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
												Nothing stands out — this task looks healthy.
											</Typography>
										)
									) : (
										<Stack spacing={1} alignItems="flex-start">
											<Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
												Get IRIS's read on this task's health and risk factors.
											</Typography>
											<Button
												size="small"
												variant="outlined"
												startIcon={<AutoAwesome sx={{ fontSize: 14 }} />}
												onClick={() => loadInsights(task.public_id)}
												sx={{
													textTransform: 'none',
													fontWeight: 700,
													fontSize: '0.78rem',
													borderRadius: '8px',
													borderColor: alpha(brand, 0.4),
													color: brand,
													'&:hover': { borderColor: brand, bgcolor: alpha(brand, 0.08) },
												}}
											>
												Get insights
											</Button>
										</Stack>
									)}
								</Box>
							</Collapse>
						</Paper>

						{/* --- ESTIMATE CARD --- */}
						<Paper elevation={0} sx={sectionCardSx}>
							{/* Card Header Row with Expand/Collapse */}
							<Stack
								direction="row"
								alignItems="center"
								justifyContent="space-between"
								onClick={() => setEstimateExpanded((prev) => !prev)}
								sx={{
									cursor: 'pointer',
									userSelect: 'none',
									py: 0.25,
								}}
							>
								<Stack direction="row" alignItems="center" spacing={1} sx={{ minWidth: 0 }}>
									<ScheduleOutlined sx={{ fontSize: 18, color: brand, flexShrink: 0 }} />
									<Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.85rem' }}>
										Estimate
									</Typography>
									{!estimateExpanded && estimate?.estimated_hours != null && (
										<Chip
											size="small"
											label={`${estimate.estimated_hours}h`}
											sx={{
												height: 20,
												fontSize: '0.72rem',
												fontWeight: 700,
												bgcolor: alpha(brand, 0.12),
												color: brand,
											}}
										/>
									)}
								</Stack>

								<Stack direction="row" alignItems="center" spacing={0.5} onClick={(e) => e.stopPropagation()}>
									{estimate && (
										<Tooltip title="Refresh estimate">
											<IconButton
												size="small"
												onClick={() => loadEstimate(task.public_id, true)}
												disabled={estimateLoading}
												sx={{ p: 0.5 }}
											>
												<RefreshOutlined sx={{ fontSize: 15 }} />
											</IconButton>
										</Tooltip>
									)}
									<Tooltip title={estimateExpanded ? 'Collapse section' : 'Expand section'}>
										<IconButton
											size="small"
											onClick={() => setEstimateExpanded((prev) => !prev)}
											sx={{ p: 0.5 }}
										>
											{estimateExpanded ? (
												<KeyboardArrowUpRounded sx={{ fontSize: 18 }} />
											) : (
												<KeyboardArrowDownRounded sx={{ fontSize: 18 }} />
											)}
										</IconButton>
									</Tooltip>
								</Stack>
							</Stack>

							{/* Card Content Collapse */}
							<Collapse in={estimateExpanded} timeout="auto" unmountOnExit>
								<Box sx={{ mt: 1.25, pt: 1, borderTop: '1px dashed', borderColor: 'divider' }}>
									{estimateLoading ? (
										<Stack spacing={0.75}>
											<Skeleton variant="text" width="50%" height={26} />
											<Skeleton variant="text" width="80%" height={16} />
										</Stack>
									) : estimate ? (
										estimate.estimated_hours != null ? (
											<Stack spacing={1}>
												<Stack direction="row" alignItems="baseline" spacing={1}>
													<Typography sx={{ fontSize: '1.45rem', fontWeight: 800, lineHeight: 1, color: brand }}>
														{estimate.estimated_hours}h
													</Typography>
													{task.estimated_hours != null && (
														<Typography variant="caption" color="text.secondary">
															currently {task.estimated_hours}h
														</Typography>
													)}
												</Stack>
												{estimate.rationale && (
													<Box
														sx={{
															maxHeight: 120,
															overflowY: 'auto',
															pr: 0.5,
															'&::-webkit-scrollbar': { width: '3px' },
															'&::-webkit-scrollbar-thumb': {
																bgcolor: alpha(theme.palette.text.primary, 0.15),
																borderRadius: '3px',
															},
														}}
													>
														<Typography
															variant="caption"
															color="text.secondary"
															sx={{ display: 'block', lineHeight: 1.45 }}
														>
															{estimate.rationale}
														</Typography>
													</Box>
												)}
												<Button
													size="small"
													variant="outlined"
													onClick={handleApplyEstimate}
													sx={{
														alignSelf: 'flex-start',
														textTransform: 'none',
														fontWeight: 700,
														fontSize: '0.78rem',
														borderRadius: '8px',
														borderColor: alpha(brand, 0.4),
														color: brand,
														'&:hover': { borderColor: brand, bgcolor: alpha(brand, 0.08) },
													}}
												>
													Apply {estimate.estimated_hours}h
												</Button>
											</Stack>
										) : (
											<Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
												Not enough data to suggest an estimate yet.
											</Typography>
										)
									) : (
										<Stack spacing={1} alignItems="flex-start">
											<Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
												Get an IRIS-suggested hour estimate for this task.
											</Typography>
											<Button
												size="small"
												variant="outlined"
												startIcon={<ScheduleOutlined sx={{ fontSize: 14 }} />}
												onClick={() => loadEstimate(task.public_id)}
												sx={{
													textTransform: 'none',
													fontWeight: 700,
													fontSize: '0.78rem',
													borderRadius: '8px',
													borderColor: alpha(brand, 0.4),
													color: brand,
													'&:hover': { borderColor: brand, bgcolor: alpha(brand, 0.08) },
												}}
											>
												Get estimate
											</Button>
										</Stack>
									)}
								</Box>
							</Collapse>
						</Paper>
					</Box>
				)}

				{/* Chat conversation area fills remaining height */}
				<Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
					<IrisChatBody
						panel={panel}
						quickActions={QUICK_ACTIONS}
						emptySubtitle="Ask me to break this task down, summarize comments, or update its fields."
					/>
				</Box>
			</Box>
		</Drawer>
	);
};

export default IrisTaskPanel;
