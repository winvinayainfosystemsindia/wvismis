import React from 'react';
import {
	Table,
	TableBody,
	TableCell,
	TableContainer,
	TableHead,
	TableRow,
	Paper,
	Typography,
	Button,
	Box,
	Stack,
	Tooltip,
	Alert,
	TextField,
	alpha,
	useTheme
} from '@mui/material';
import {
	Add as AddIcon,
	BeachAccess as HolidayIcon,
	Error as RejectedIcon,
	LockOutlined as LockIcon,
	WarningAmberOutlined as OvertimeIcon,
	SendOutlined as SubmitDayIcon,
	UndoOutlined as RevokeIcon,
	CheckCircleOutline as ApprovedCheckIcon,
	TaskAltOutlined as SubmittedCheckIcon,
} from '@mui/icons-material';
import type { ProjectTimeLog, OrgHoliday, TimesheetWeekUnlockRequest } from '../../../models/timesheet';
import { DEFAULT_WEEKLY_HOURS_TARGET } from '../../../models/timesheet';
import TimesheetStatusBadge from '../shared/TimesheetStatusBadge';
import { BaseDialog } from '../../common/dialogbox';
import { DataTableEmpty } from '../../common/table';
import { AddButton } from '../../common/button';
import { useWeeklyTimesheetGrid } from './hooks/useWeeklyTimesheetGrid';
import { formatHoursDisplay } from './utils';

interface WeeklyTimesheetGridProps {
	dates: Date[];
	logs: ProjectTimeLog[];
	holidays: OrgHoliday[];
	onCellClick: (dateStr: string, log?: ProjectTimeLog) => void;
	onAddRow: () => void;
	onSubmitWeek: () => void;
	onSubmitDay?: (dateStr: string) => void;
	submitLoading: boolean;
	reportingManagerSet: boolean;
	/** False once the viewed week has fully ended. */
	isCurrentWeek: boolean;
	/** The current user's own unlock/revoke requests, across all weeks -- filtered internally to this week. */
	myUnlockRequests: TimesheetWeekUnlockRequest[];
	onRequestUnlock: (reason?: string, requestType?: 'unlock' | 'revoke') => void;
	unlockRequestLoading: boolean;
	/** Manager-granted exception to log time on holidays/Sundays -- without it, holiday cells are read-only. */
	canLogOnHolidays: boolean;
	/** From the user's own TimesheetUserSettings; falls back to DEFAULT_WEEKLY_HOURS_TARGET when unset. */
	weeklyHoursTarget?: number;
	/** Callback to open reporting manager assignment dialog */
	onAssignReportingManager?: () => void;
}

const WeeklyTimesheetGrid: React.FC<WeeklyTimesheetGridProps> = ({
	dates,
	logs,
	holidays,
	onCellClick,
	onAddRow,
	onSubmitWeek,
	onSubmitDay,
	submitLoading,
	reportingManagerSet,
	isCurrentWeek,
	myUnlockRequests,
	onRequestUnlock,
	unlockRequestLoading,
	canLogOnHolidays,
	weeklyHoursTarget,
	onAssignReportingManager
}) => {
	const theme = useTheme();
	const target = weeklyHoursTarget ?? DEFAULT_WEEKLY_HOURS_TARGET;
	const isDark = theme.palette.mode === 'dark';

	const {
		requestDialogOpen, setRequestDialogOpen,
		requestDialogMode,
		requestReason, setRequestReason,
		requestReasonError, setRequestReasonError,
		dateStrings,
		todayStr,
		isFreeEditWeek,
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
		hasApprovedOrSubmitted,
		grandTotal,
		isLocked,
		pendingRequest,
		latestDenied,
		activeGrant,
		handleOpenRequestDialog,
		handleSubmitUnlockRequest
	} = useWeeklyTimesheetGrid({
		dates,
		logs,
		holidays,
		myUnlockRequests,
		onRequestUnlock,
		isCurrentWeek
	});

	const todayInWeek = dateStrings.includes(todayStr);
	const todayUnsubmittedCount = unsubmittedByDay[todayStr] || 0;

	return (
		<Stack spacing={3}>
			{/* Grid Header Actions */}
			<Stack
				direction={{ xs: 'column', sm: 'row' }}
				justifyContent="space-between"
				alignItems={{ xs: 'stretch', sm: 'center' }}
				gap={2}
				sx={{
					border: '1px solid',
					borderColor: 'divider',
					borderRadius: theme.layout.radius.card,
					bgcolor: 'background.paper',
					p: 2
				}}
			>
				<Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap" rowGap={1}>
					<Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
						Week Status:
					</Typography>
					<TimesheetStatusBadge status={weeklyStatus} size="medium" />
					{logs.length > 0 && logs[0].rejection_note && weeklyStatus === 'rejected' && (
						<Tooltip title={logs[0].rejection_note}>
							<Box sx={{ display: 'flex', alignItems: 'center', color: 'error.main', cursor: 'help' }}>
								<RejectedIcon fontSize="small" sx={{ mr: 0.5 }} />
								<Typography variant="caption" sx={{ fontWeight: 600 }}>Rejection Reason</Typography>
							</Box>
						</Tooltip>
					)}
					<Box sx={{ width: '1px', height: 20, bgcolor: 'divider' }} />
					<Typography variant="body2" sx={{ fontWeight: 700, color: grandTotal > target ? 'warning.main' : 'text.secondary' }}>
						{formatHoursDisplay(grandTotal)} / {formatHoursDisplay(target)}h target
					</Typography>
					{grandTotal > target && (
						<Tooltip title={`${formatHoursDisplay(grandTotal - target)}h over your ${formatHoursDisplay(target)}h weekly target`}>
							<Box sx={{ display: 'flex', alignItems: 'center', color: 'warning.main', cursor: 'help' }}>
								<OvertimeIcon fontSize="small" sx={{ mr: 0.5 }} />
								<Typography variant="caption" sx={{ fontWeight: 700 }}>Overtime</Typography>
							</Box>
						</Tooltip>
					)}
				</Stack>

				<Stack direction="row" spacing={1.5} width={{ xs: '100%', sm: 'auto' }} flexWrap="wrap" useFlexGap>
					<Button
						variant="outlined"
						startIcon={<AddIcon />}
						onClick={onAddRow}
						disabled={isLocked || isWeekClosed}
						sx={{ borderRadius: '10px', px: 2.5, fontWeight: 700 }}
					>
						Add Row
					</Button>
					{hasApprovedOrSubmitted && !pendingRequest && (
						<Tooltip title="Wrongly submitted time? Request your allocated reporting manager or admin to revoke this submission back to Draft.">
							<span>
								<Button
									variant="outlined"
									color="warning"
									startIcon={<RevokeIcon />}
									onClick={() => handleOpenRequestDialog('revoke')}
									disabled={unlockRequestLoading || !reportingManagerSet}
									sx={{ borderRadius: '10px', px: 2, fontWeight: 700, textTransform: 'none' }}
								>
									Request Revoke
								</Button>
							</span>
						</Tooltip>
					)}
					{todayInWeek && todayUnsubmittedCount > 0 && onSubmitDay && (
						<Button
							variant="outlined"
							color="primary"
							startIcon={<SubmitDayIcon />}
							onClick={() => onSubmitDay(todayStr)}
							disabled={submitLoading || !reportingManagerSet || isLocked}
							sx={{ borderRadius: '10px', px: 2, fontWeight: 700, textTransform: 'none' }}
						>
							Submit Today ({todayUnsubmittedCount})
						</Button>
					)}
					{hasUnsubmittedEntries && (
						<AddButton
							hideIcon
							onClick={onSubmitWeek}
							disabled={submitLoading || !reportingManagerSet || isLocked}
							sx={{ px: 3 }}
						>
							Submit Week
						</AddButton>
					)}
				</Stack>
			</Stack>

			{!reportingManagerSet && (
				<Alert
					severity="warning"
					variant="outlined"
					sx={{ borderRadius: theme.layout.radius.card }}
					action={
						onAssignReportingManager && (
							<Button
								color="warning"
								variant="contained"
								size="small"
								onClick={onAssignReportingManager}
								sx={{ fontWeight: 700, whiteSpace: 'nowrap', textTransform: 'none', borderRadius: '8px' }}
							>
								Assign Reporting Manager
							</Button>
						)
					}
				>
					<Typography variant="body2" sx={{ fontWeight: 700 }}>
						Submission blocked
					</Typography>
					<Typography variant="body2" color="text.secondary">
						You don't have a Reporting Manager assigned. Select a manager to submit weekly timesheets for approval.
					</Typography>
				</Alert>
			)}

			{isLocked && (
				<Alert
					severity={pendingRequest ? 'info' : 'warning'}
					icon={<LockIcon fontSize="inherit" />}
					action={
						!pendingRequest && (
							<Button
								color="inherit"
								size="small"
								onClick={() => handleOpenRequestDialog('unlock')}
								disabled={unlockRequestLoading}
								sx={{ fontWeight: 700, whiteSpace: 'nowrap' }}
							>
								Request Access
							</Button>
						)
					}
					sx={{ borderRadius: 4 }}
				>
					{pendingRequest ? (
						<>Unlock request sent to your manager on {pendingRequest.created_at.split('T')[0]} — waiting for approval.</>
					) : (
						<>
							This week is older than the previous week and wasn't submitted in time, so it's locked. Request access from your manager to add or edit entries.
							{latestDenied && (
								<Typography variant="caption" display="block" sx={{ mt: 0.5, fontStyle: 'italic' }}>
									Your last request was denied{latestDenied.resolution_note ? `: ${latestDenied.resolution_note}` : '.'}
								</Typography>
							)}
						</>
					)}
				</Alert>
			)}

			{!isLocked && pendingRequest && (
				<Alert severity="info" sx={{ borderRadius: 4 }}>
					{pendingRequest.request_type === 'revoke'
						? `Revoke request sent to your allocated manager/admin on ${pendingRequest.created_at.split('T')[0]} — waiting for approval to revert submitted entries to Draft.`
						: `Unlock request sent to your manager on ${pendingRequest.created_at.split('T')[0]} — waiting for approval.`}
				</Alert>
			)}

			{hasApprovedEntries && !pendingRequest && (
				<Alert
					severity="success"
					sx={{ borderRadius: 4 }}
					action={
						<Button
							color="inherit"
							size="small"
							startIcon={<RevokeIcon fontSize="small" />}
							onClick={() => handleOpenRequestDialog('revoke')}
							disabled={unlockRequestLoading || !reportingManagerSet}
							sx={{ fontWeight: 700, whiteSpace: 'nowrap', textTransform: 'none' }}
						>
							Request Revoke
						</Button>
					}
				>
					This week has received final weekly approval from your manager. Need to correct an entry? Request a revoke from your manager or admin.
				</Alert>
			)}

			{isFreeEditWeek && !hasApprovedEntries && weeklyStatus === 'submitted' && (
				<Alert severity="info" sx={{ borderRadius: 4 }}>
					Daily entries submitted. You can still modify submitted entries for the previous day and previous week without manager permission before final weekly approval, or click <strong>Request Revoke</strong> to pull the submission back to Draft.
				</Alert>
			)}

			{activeGrant && !isCurrentWeek && (
				<Alert severity="success" sx={{ borderRadius: 4 }}>
					Your manager unlocked this week — add/edit your entries and hit Submit Week when ready.
				</Alert>
			)}

			{hasUnsubmittedEntries && (weeklyStatus === 'submitted' || weeklyStatus === 'approved') && (
				<Alert severity="info" sx={{ borderRadius: 4 }}>
					You've added entries since your last submission — hit Submit Week to send them to your manager too.
				</Alert>
			)}

			<TableContainer
				component={Paper}
				elevation={1}
				sx={{
					border: 1,
					borderColor: 'divider',
					borderRadius: theme.layout.radius.card,
					overflow: 'hidden',
					bgcolor: 'background.paper'
				}}
			>
				<Table sx={{ width: '100%', minWidth: 760, tableLayout: 'fixed' }}>
					<TableHead>
						<TableRow sx={{ bgcolor: 'action.hover' }}>
							<TableCell sx={{ fontWeight: 700, width: '23%' }}>Log Target</TableCell>
							<TableCell sx={{ fontWeight: 700, width: '8%', whiteSpace: 'nowrap' }}>Billing</TableCell>
							{dates.map((date, i) => {
								const dStr = dateStrings[i];
								const isHoliday = isHolidayDate(dStr);
								const isToday = dStr === todayStr;
								const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
								const dayNum = date.getDate();

								return (
									<TableCell
										key={dStr}
										align="center"
										sx={{
											fontWeight: 700,
											width: '8%',
											px: 0.5,
											whiteSpace: 'nowrap',
											position: 'relative',
											color: isToday ? 'primary.main' : 'inherit',
											bgcolor: isHoliday
												? alpha(theme.palette.warning.main, isDark ? 0.08 : 0.05)
												: isToday
													? alpha(theme.palette.primary.main, isDark ? 0.1 : 0.06)
													: 'inherit',
											'&::after': isToday
												? {
													content: '""',
													position: 'absolute',
													top: 0,
													left: 0,
													right: 0,
													height: 2,
													bgcolor: 'primary.main'
												}
												: undefined
										}}
									>
										<Stack direction="column" spacing={0.5} alignItems="center" justifyContent="center">
											<Stack direction="row" spacing={0.25} justifyContent="center" alignItems="center">
												<Typography variant="body2" sx={{ fontWeight: 700, whiteSpace: 'nowrap' }}>
													{dayName} {dayNum}
												</Typography>
												{isHoliday && (
													<Tooltip title={`Holiday: ${holidayLabel(dStr)}`}>
														<HolidayIcon sx={{ fontSize: '0.85rem', color: 'warning.main', flexShrink: 0 }} />
													</Tooltip>
												)}
												{dayStatusMap[dStr] === 'approved' && (
													<Tooltip title="Day approved by manager">
														<ApprovedCheckIcon sx={{ fontSize: '0.9rem', color: 'success.main' }} />
													</Tooltip>
												)}
												{dayStatusMap[dStr] === 'submitted' && (
													<Tooltip title="Day submitted (weekly manager approval pending)">
														<SubmittedCheckIcon sx={{ fontSize: '0.9rem', color: 'warning.main' }} />
													</Tooltip>
												)}
											</Stack>
											{unsubmittedByDay[dStr] > 0 && dStr <= todayStr && !isLocked && !isWeekClosed && onSubmitDay && (
												<Tooltip
													title={
														reportingManagerSet
															? `Submit ${unsubmittedByDay[dStr]} entry(s) for ${dayName} ${dayNum}`
															: 'Assign a Reporting Manager to submit daily entries'
													}
												>
													<span>
														<Button
															size="small"
															variant="text"
															color="primary"
															disabled={submitLoading || !reportingManagerSet}
															onClick={(e) => {
																e.stopPropagation();
																onSubmitDay(dStr);
															}}
															sx={{
																minWidth: 'auto',
																px: 0.75,
																py: 0.1,
																fontSize: '0.68rem',
																fontWeight: 700,
																lineHeight: 1.3,
																borderRadius: '6px',
																textTransform: 'none',
																bgcolor: alpha(theme.palette.primary.main, 0.08),
																'&:hover': {
																	bgcolor: alpha(theme.palette.primary.main, 0.16)
																}
															}}
														>
															Submit Day
														</Button>
													</span>
												</Tooltip>
											)}
										</Stack>
									</TableCell>
								);
							})}
							<TableCell align="center" sx={{ fontWeight: 700, width: '13%', px: 1, whiteSpace: 'nowrap' }}>Total</TableCell>
						</TableRow>
					</TableHead>
					<TableBody>
						{gridRows.length === 0 ? (
							<DataTableEmpty
								colSpan={dates.length + 3}
								message="No hours logged for this week"
								subMessage='Click "Add Row" or click a date cell below to log time'
							/>
						) : (
							gridRows.map((row) => (
								<TableRow
									key={row.id}
									sx={{
										'&:hover': { bgcolor: 'action.hover' },
										transition: 'background-color 0.2s'
									}}
								>
									<TableCell
										sx={{
											py: 1.5,
											borderLeft: '3px solid',
											borderLeftColor: row.type === 'general' ? 'info.main' : 'primary.main'
										}}
									>
										{row.type === 'project_task' && (
											<Box>
												<Typography variant="body2" sx={{ fontWeight: 700 }}>
													{row.projectName}
												</Typography>
												<Typography variant="caption" color="text.secondary" display="block">
													Task: {row.taskTitle}
												</Typography>
											</Box>
										)}
										{row.type === 'project_only' && (
											<Box>
												<Typography variant="body2" sx={{ fontWeight: 700 }}>
													{row.projectName}
												</Typography>
												<Typography variant="caption" color="primary.main" sx={{ fontWeight: 600 }}>
													Project Only
												</Typography>
											</Box>
										)}
										{row.type === 'general' && (
											<Box>
												<Typography variant="body2" sx={{ fontWeight: 700, color: 'text.secondary' }}>
													General: {row.categoryName}
												</Typography>
											</Box>
										)}
									</TableCell>
									<TableCell>
										<Typography
											variant="caption"
											sx={{
												fontWeight: 700,
												color: row.billingType === 'billable' ? 'success.main' : 'text.secondary',
												textTransform: 'uppercase'
											}}
										>
											{row.billingType === 'billable' ? 'Billable' : 'Non-Bill'}
										</Typography>
									</TableCell>
									{dateStrings.map((dateStr) => {
										const log = row.cells[dateStr];
										const isHoliday = isHolidayDate(dateStr);
										const isToday = dateStr === todayStr;
										const isFutureDate = dateStr > todayStr;
										const isApproved = log?.status === 'approved';
										const isSubmitted = log?.status === 'submitted';
										const isHolidayBlocked = isHoliday && !canLogOnHolidays;
										// Submitted entries in the current week (including previous day) and previous week
										// can be modified directly without manager permission until final weekly approval.
										const canModifySubmitted = isSubmitted && (isFreeEditWeek || !!activeGrant) && !hasApprovedEntries;
										const isCellDisabled =
											isFutureDate ||
											(log && isApproved) ||
											(log && isSubmitted && !canModifySubmitted) ||
											isLocked ||
											isHolidayBlocked ||
											isWeekClosed;

										return (
											<TableCell
												key={dateStr}
												align="center"
												onClick={() => {
													if (isCellDisabled) return;
													onCellClick(dateStr, log);
												}}
												sx={{
													cursor: isCellDisabled ? 'default' : 'pointer',
													p: 1,
													position: 'relative',
													bgcolor: isHoliday
														? alpha(theme.palette.warning.main, isDark ? 0.04 : 0.02)
														: isToday
															? alpha(theme.palette.primary.main, isDark ? 0.05 : 0.03)
															: 'inherit',
													borderRight: 1,
													borderColor: 'divider',
													opacity: isHolidayBlocked && !log ? 0.6 : 1,
													'&:hover': {
														bgcolor: isCellDisabled ? 'inherit' : 'action.hover'
													}
												}}
											>
												{log ? (
													<Box
														sx={{
															py: 1,
															px: 0.5,
															borderRadius: 3,
															bgcolor: isApproved
																? alpha(theme.palette.success.main, isDark ? 0.1 : 0.05)
																: isSubmitted
																? alpha(theme.palette.warning.main, isDark ? 0.1 : 0.05)
																: 'action.selected',
															border: `1px solid ${
																isApproved
																	? alpha(theme.palette.success.main, 0.3)
																	: isSubmitted
																	? alpha(theme.palette.warning.main, 0.3)
																	: 'transparent'
															}`,
															display: 'flex',
															flexDirection: 'column',
															alignItems: 'center',
															gap: 0.5
														}}
													>
														<Typography variant="body2" sx={{ fontWeight: 700 }}>
															{formatHoursDisplay(log.hours)}
														</Typography>
														{log.is_holiday_override && (
															<HolidayIcon sx={{ fontSize: '0.75rem', color: 'warning.main' }} />
														)}
													</Box>
												) : (
													<Typography variant="body2" color="text.secondary" sx={{ opacity: 0.2 }}>
														—
													</Typography>
												)}
											</TableCell>
										);
									})}
									<TableCell align="center" sx={{ px: 1, whiteSpace: 'nowrap' }}>
										<Typography variant="subtitle2" sx={{ fontWeight: 800, whiteSpace: 'nowrap' }}>
											{formatHoursDisplay(row.totalHours)}
										</Typography>
									</TableCell>
								</TableRow>
							))
						)}

						{/* Day Totals Row */}
						<TableRow
							sx={{
								bgcolor: alpha(theme.palette.primary.main, isDark ? 0.08 : 0.05),
								borderTop: '2px solid',
								borderColor: 'primary.main'
							}}
						>
							<TableCell colSpan={2} sx={{ fontWeight: 800 }}>
								Total Hours
							</TableCell>
							{dateStrings.map((dateStr) => (
								<TableCell key={dateStr} align="center" sx={{ fontWeight: 800, px: 0.5, whiteSpace: 'nowrap' }}>
									{formatHoursDisplay(dayTotals[dateStr])}
								</TableCell>
							))}
							<TableCell align="center" sx={{ fontWeight: 900, fontSize: '1rem', color: 'primary.main', px: 1, whiteSpace: 'nowrap' }}>
								{formatHoursDisplay(grandTotal)}
							</TableCell>
						</TableRow>
					</TableBody>
				</Table>
			</TableContainer>

			<BaseDialog
				open={requestDialogOpen}
				onClose={() => setRequestDialogOpen(false)}
				title={requestDialogMode === 'revoke' ? 'Request Timesheet Revoke' : 'Request Manager Access'}
				maxWidth="xs"
				actions={
					<>
						<Button onClick={() => setRequestDialogOpen(false)} variant="outlined" sx={{ borderRadius: 3 }}>
							Cancel
						</Button>
						<Button
							onClick={handleSubmitUnlockRequest}
							variant="contained"
							color={requestDialogMode === 'revoke' ? 'warning' : 'primary'}
							disabled={unlockRequestLoading}
							sx={{ borderRadius: 3, fontWeight: 700 }}
						>
							{requestDialogMode === 'revoke' ? 'Submit Revoke Request' : 'Send Request'}
						</Button>
					</>
				}
			>
				<Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
					{requestDialogMode === 'revoke'
						? 'Your allocated reporting manager (or admin) will review this request. Once approved, all submitted/approved entries for this week will be reverted to Draft so you can correct and resubmit them.'
						: "Your manager will be asked to unlock this week so you can add/edit and submit it. Let them know why it's late (optional)."}
				</Typography>
				<TextField
					label={requestDialogMode === 'revoke' ? 'Reason for Revoke (required)' : 'Reason (optional)'}
					required={requestDialogMode === 'revoke'}
					error={!!requestReasonError}
					helperText={requestReasonError || undefined}
					multiline
					rows={3}
					value={requestReason}
					onChange={(e) => {
						setRequestReason(e.target.value);
						if (requestReasonError) setRequestReasonError(null);
					}}
					fullWidth
					autoFocus
					placeholder={
						requestDialogMode === 'revoke'
							? 'e.g. Logged hours under the wrong project/task and need to revise.'
							: 'e.g. I was on leave and missed the submission window.'
					}
				/>
			</BaseDialog>
		</Stack>
	);
};

export default WeeklyTimesheetGrid;
