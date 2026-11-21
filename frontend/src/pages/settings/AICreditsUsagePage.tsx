import React, { useEffect, useState } from 'react';
import {
	Box,
	Grid,
	Card,
	CardContent,
	Typography,
	Stack,
	Button,
	Chip,
	LinearProgress,
	CircularProgress,
	Dialog,
	DialogTitle,
	DialogContent,
	DialogActions,
	TextField,
	Alert,
	InputAdornment,
	useTheme,
	alpha,
	Divider,
} from '@mui/material';
import {
	BoltOutlined as BoltIcon,
	TrendingUpOutlined as TrendingIcon,
	ForumOutlined as ChatIcon,
	TokenOutlined as TokenIcon,
	CreditCard as CardIcon,
	AutoAwesome as SparklesIcon,
	CheckCircleOutline as CheckIcon,
	Schedule as ClockIcon,
	InfoOutlined as InfoIcon,
	ShoppingBagOutlined as BuyIcon,
} from '@mui/icons-material';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useNavigate } from '../../router/tanstackCompat';
import PageHeader from '../../components/common/page-header';
import useToast from '../../hooks/useToast';
import { useAppDispatch, useAppSelector } from '../../store/hooks';
import { fetchCreditBalance, fetchUsageSummary, setCreditBalance } from '../../store/slices/aiSlice';
import aiService from '../../services/aiService';

const prettifyActionType = (actionType: string): string =>
	actionType
		.replace(/_/g, ' ')
		.replace(/\b\w/g, (c) => c.toUpperCase());

const formatINR = (amount: number) => `₹${amount.toLocaleString('en-IN')}`;

interface CreditPackage {
	credits: number;
	price: number;
	effectiveRate: string;
	popular?: boolean;
	perks: string[];
}

const CREDIT_PACKAGES: CreditPackage[] = [
	{
		credits: 100,
		price: 99,
		effectiveRate: '₹0.99 / credit',
		perks: ['Instant wallet credit', 'Never expires across months', 'Valid for all AI models'],
	},
	{
		credits: 500,
		price: 399,
		effectiveRate: '₹0.80 / credit',
		popular: true,
		perks: ['20% savings vs base', 'Instant wallet credit', 'Priority agent execution', 'Valid for all AI models'],
	},
	{
		credits: 1000,
		price: 699,
		effectiveRate: '₹0.70 / credit',
		perks: ['30% savings vs base', 'Instant wallet credit', 'Priority agent execution', 'Valid for all AI models'],
	},
	{
		credits: 2500,
		price: 1499,
		effectiveRate: '₹0.60 / credit',
		perks: ['40% bulk discount', 'Instant wallet credit', 'High-volume analysis', 'Valid for all AI models'],
	},
];

interface MetricCardProps {
	icon: React.ReactNode;
	label: string;
	value: string | number;
	subtitle: string;
	color?: string;
	badge?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ icon, label, value, subtitle, color, badge }) => {
	const theme = useTheme();
	const isDark = theme.palette.mode === 'dark';
	const accentColor = color || theme.palette.primary.main;

	return (
		<Card
			sx={{
				borderRadius: '16px',
				border: `1px solid ${theme.palette.divider}`,
				background: theme.gradients?.card || theme.palette.background.paper,
				backdropFilter: 'blur(16px)',
				boxShadow: isDark
					? '0 8px 24px -4px rgba(0, 0, 0, 0.4)'
					: '0 4px 20px -2px rgba(139, 124, 246, 0.05)',
				transition: 'transform 0.2s ease, box-shadow 0.2s ease',
				'&:hover': {
					transform: 'translateY(-2px)',
					boxShadow: isDark
						? '0 12px 30px -4px rgba(0, 0, 0, 0.5)'
						: '0 8px 28px -2px rgba(139, 124, 246, 0.1)',
				},
				height: '100%',
			}}
		>
			<CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
				<Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
					<Box
						sx={{
							width: 40,
							height: 40,
							borderRadius: '12px',
							bgcolor: alpha(accentColor, 0.12),
							color: accentColor,
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center',
						}}
					>
						{icon}
					</Box>
					{badge && (
						<Chip
							label={badge}
							size="small"
							sx={{
								height: 22,
								fontSize: '0.68rem',
								fontWeight: 700,
								bgcolor: alpha(accentColor, 0.12),
								color: accentColor,
								border: `1px solid ${alpha(accentColor, 0.2)}`,
							}}
						/>
					)}
				</Stack>
				<Typography
					variant="caption"
					sx={{
						fontWeight: 700,
						color: 'text.secondary',
						textTransform: 'uppercase',
						letterSpacing: '0.05em',
						display: 'block',
						mb: 0.5,
					}}
				>
					{label}
				</Typography>
				<Typography variant="h4" sx={{ fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em', mb: 0.5 }}>
					{value}
				</Typography>
				<Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 500 }}>
					{subtitle}
				</Typography>
			</CardContent>
		</Card>
	);
};

const AICreditsUsagePage: React.FC = () => {
	const theme = useTheme();
	const navigate = useNavigate();
	const isDark = theme.palette.mode === 'dark';
	const brand = theme.palette.primary.main;
	const toast = useToast();
	const dispatch = useAppDispatch();
	const user = useAppSelector((state) => state.auth.user);
	const planName = user?.organization?.plan?.name || (user?.organization as any)?.subscription_plan || 'Enterprise';

	const balance = useAppSelector((state) => state.ai.creditBalance);
	const usage = useAppSelector((state) => state.ai.usageSummary);
	const lastFetched = useAppSelector((state) => state.ai.lastFetched);
	const [loading, setLoading] = useState(!balance);

	// Checkout / Buy-credits dialog state
	const [selectedPackage, setSelectedPackage] = useState<CreditPackage | null>(null);
	const [paymentDialogOpen, setPaymentDialogOpen] = useState(false);
	const [processingPayment, setProcessingPayment] = useState(false);
	const [cardNumber, setCardNumber] = useState('');
	const [cardExpiry, setCardExpiry] = useState('');
	const [cardCvc, setCardCvc] = useState('');
	const [cardName, setCardName] = useState('');

	useEffect(() => {
		const isStale = !lastFetched || Date.now() - lastFetched > 25000;
		if (!balance || isStale) {
			Promise.all([
				dispatch(fetchCreditBalance(false)),
				dispatch(fetchUsageSummary('mine')),
			]).finally(() => setLoading(false));
		} else {
			setLoading(false);
		}
	}, [dispatch, balance, lastFetched]);

	const handleBuyClick = (pkg: CreditPackage) => {
		setSelectedPackage(pkg);
		setCardNumber('');
		setCardExpiry('');
		setCardCvc('');
		setCardName(user?.full_name || '');
		setPaymentDialogOpen(true);
	};

	const handlePaymentSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (!selectedPackage) return;
		if (!cardNumber || !cardExpiry || !cardCvc || !cardName) {
			toast.error('Please fill in all card details.');
			return;
		}

		setProcessingPayment(true);
		setTimeout(async () => {
			try {
				const updated = await aiService.purchaseCredits(selectedPackage.credits);
				dispatch(setCreditBalance(updated));
				toast.success(`Payment confirmed! ${selectedPackage.credits.toLocaleString()} credits added to your wallet.`);
				setPaymentDialogOpen(false);
			} catch (error: any) {
				toast.error(
					error?.response?.data?.error?.message || error?.message || 'Payment processing failed. Please try again.'
				);
			} finally {
				setProcessingPayment(false);
			}
		}, 1800);
	};

	if (loading) {
		return (
			<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
				<CircularProgress />
			</Box>
		);
	}

	const resetsOn = (() => {
		if (!balance) return null;
		const d = new Date(balance.period_start);
		d.setMonth(d.getMonth() + 1);
		return d;
	})();

	const daysUntilReset = (() => {
		if (!resetsOn) return null;
		const now = new Date();
		const diffMs = resetsOn.getTime() - now.getTime();
		return Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));
	})();

	const chartData = (usage?.daily_trend || []).map((d) => ({
		date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
		credits: d.credits,
	}));

	const actionRows = [...(usage?.by_action_type || [])].sort((a, b) => b.credits - a.credits);
	const maxActionCredits = Math.max(...actionRows.map((r) => r.credits), 1);

	const percentUsed = Math.min(balance?.percent_used ?? 0, 100);
	const percentRemaining = Math.max(0, 100 - percentUsed);

	return (
		<Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 3 }}>
			{/* Page Header with Action Buttons */}
			<PageHeader
				title="AI Credits & Operations"
				subtitle="Monitor your monthly AI quota consumption, analyze token metrics, and top up wallet credits."
				action={
					<Stack direction="row" spacing={1.5} alignItems="center">
						<Button
							variant="outlined"
							size="medium"
							onClick={() => navigate('/billing')}
							sx={{
								textTransform: 'none',
								fontWeight: 600,
								borderRadius: '10px',
								borderColor: theme.palette.divider,
								color: 'text.primary',
								'&:hover': {
									borderColor: theme.palette.primary.main,
									bgcolor: alpha(theme.palette.primary.main, 0.04),
								},
							}}
						>
							Subscription Plan
						</Button>
						<Button
							variant="contained"
							size="medium"
							startIcon={<BuyIcon />}
							onClick={() => {
								const target = document.getElementById('topup-packages-section');
								target?.scrollIntoView({ behavior: 'smooth' });
							}}
							sx={{
								textTransform: 'none',
								fontWeight: 700,
								borderRadius: '10px',
								background: theme.gradients?.brand || theme.palette.primary.main,
								boxShadow: 'none',
								px: 2.5,
							}}
						>
							Top Up Credits
						</Button>
					</Stack>
				}
				mb={0}
			/>

			{/* Hero Balance & Active Quota Card */}
			<Card
				sx={{
					borderRadius: '20px',
					border: `1px solid ${theme.palette.divider}`,
					background: isDark
						? 'linear-gradient(135deg, rgba(30, 27, 75, 0.45) 0%, rgba(15, 23, 42, 0.6) 100%)'
						: 'linear-gradient(135deg, rgba(238, 242, 255, 0.8) 0%, rgba(255, 255, 255, 0.95) 100%)',
					backdropFilter: 'blur(20px)',
					boxShadow: isDark
						? '0 12px 36px 0 rgba(0, 0, 0, 0.35)'
						: '0 8px 32px 0 rgba(99, 102, 241, 0.06)',
					overflow: 'hidden',
					position: 'relative',
				}}
			>
				{/* Background decorative accent glow */}
				<Box
					sx={{
						position: 'absolute',
						top: -50,
						right: -50,
						width: 200,
						height: 200,
						borderRadius: '50%',
						background: `radial-gradient(circle, ${alpha(brand, 0.15)} 0%, transparent 70%)`,
						pointerEvents: 'none',
					}}
				/>

				<CardContent sx={{ p: { xs: 2.5, sm: 3.5 } }}>
					<Grid container spacing={3} alignItems="center">
						{/* Left: Active Credit Balance */}
						<Grid size={{ xs: 12, md: 7 }}>
							<Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 1.5 }}>
								<Box
									sx={{
										width: 48,
										height: 48,
										borderRadius: '14px',
										background: theme.gradients?.brandDiagonal || theme.palette.primary.main,
										display: 'flex',
										alignItems: 'center',
										justifyContent: 'center',
										boxShadow: `0 6px 16px ${alpha(brand, 0.3)}`,
									}}
								>
									<BoltIcon sx={{ color: '#ffffff', fontSize: 28 }} />
								</Box>
								<Box>
									<Stack direction="row" alignItems="center" spacing={1}>
										<Typography variant="h3" sx={{ fontWeight: 800, color: 'text.primary', lineHeight: 1.1 }}>
											{(balance?.balance ?? 0).toLocaleString()}
										</Typography>
										<Typography variant="h6" sx={{ color: 'text.secondary', fontWeight: 600 }}>
											credits available
										</Typography>
									</Stack>
									<Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
										Allocated from your <strong>{planName}</strong> plan ({(balance?.granted ?? 0).toLocaleString()} monthly limit)
									</Typography>
								</Box>
							</Stack>

							{/* Progress Bar with Tooltip */}
							<Box sx={{ mt: 2.5, maxWidth: 540 }}>
								<Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
									<Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>
										Quota Utilization
									</Typography>
									<Typography variant="caption" sx={{ fontWeight: 800, color: percentUsed >= 90 ? 'error.main' : 'text.primary' }}>
										{percentUsed.toFixed(1)}% consumed ({((balance?.granted ?? 0) - (balance?.balance ?? 0)).toLocaleString()} / {(balance?.granted ?? 0).toLocaleString()})
									</Typography>
								</Stack>
								<LinearProgress
									variant="determinate"
									value={percentUsed}
									sx={{
										height: 10,
										borderRadius: 5,
										bgcolor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)',
										'& .MuiLinearProgress-bar': {
											borderRadius: 5,
											background:
												percentUsed >= 90
													? theme.palette.error.main
													: percentUsed >= 75
													? theme.palette.warning.main
													: theme.gradients?.brand || brand,
										},
									}}
								/>
							</Box>
						</Grid>

						{/* Right: Quick Meta Stats */}
						<Grid size={{ xs: 12, md: 5 }}>
							<Box
								sx={{
									p: 2.5,
									borderRadius: '16px',
									bgcolor: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(255, 255, 255, 0.7)',
									border: `1px solid ${theme.palette.divider}`,
									display: 'flex',
									flexDirection: 'column',
									gap: 1.5,
								}}
							>
								<Stack direction="row" justifyContent="space-between" alignItems="center">
									<Stack direction="row" spacing={1} alignItems="center">
										<ClockIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
										<Typography variant="body2" color="text.secondary">
											Billing Cycle Reset
										</Typography>
									</Stack>
									<Typography variant="body2" sx={{ fontWeight: 700 }}>
										{resetsOn ? resetsOn.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : 'Next month'}
										{daysUntilReset !== null && ` (${daysUntilReset} days)`}
									</Typography>
								</Stack>

								<Divider sx={{ borderStyle: 'dashed' }} />

								<Stack direction="row" justifyContent="space-between" alignItems="center">
									<Stack direction="row" spacing={1} alignItems="center">
										<SparklesIcon sx={{ fontSize: 18, color: brand }} />
										<Typography variant="body2" color="text.secondary">
											Active Plan Tier
										</Typography>
									</Stack>
									<Chip
										label={`${planName} Tier`}
										size="small"
										sx={{
											fontWeight: 800,
											fontSize: '0.72rem',
											bgcolor: alpha(brand, 0.12),
											color: brand,
											border: `1px solid ${alpha(brand, 0.2)}`,
										}}
									/>
								</Stack>

								<Divider sx={{ borderStyle: 'dashed' }} />

								<Stack direction="row" justifyContent="space-between" alignItems="center">
									<Typography variant="body2" color="text.secondary">
										Rollover Status
									</Typography>
									<Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>
										Automatic 1st of every month
									</Typography>
								</Stack>
							</Box>
						</Grid>
					</Grid>
				</CardContent>
			</Card>

			{/* 4 Metric Cards */}
			<Grid container spacing={2}>
				<Grid size={{ xs: 12, sm: 6, lg: 3 }}>
					<MetricCard
						icon={<BoltIcon />}
						label="Available Balance"
						value={(balance?.balance ?? 0).toLocaleString()}
						subtitle={`${percentRemaining.toFixed(0)}% remaining of this month`}
						color={theme.palette.primary.main}
						badge="Active"
					/>
				</Grid>
				<Grid size={{ xs: 12, sm: 6, lg: 3 }}>
					<MetricCard
						icon={<TrendingIcon />}
						label="Credits Used"
						value={(usage?.total_credits_consumed ?? 0).toLocaleString()}
						subtitle="Consumed in current period"
						color={theme.palette.info.main}
					/>
				</Grid>
				<Grid size={{ xs: 12, sm: 6, lg: 3 }}>
					<MetricCard
						icon={<ChatIcon />}
						label="AI Operations"
						value={(usage?.total_calls ?? 0).toLocaleString()}
						subtitle="Agent & completion tasks"
						color={theme.palette.success.main}
					/>
				</Grid>
				<Grid size={{ xs: 12, sm: 6, lg: 3 }}>
					<MetricCard
						icon={<TokenIcon />}
						label="Tokens Metered"
						value={(usage?.total_tokens_used ?? 0).toLocaleString()}
						subtitle="Prompt & response volume"
						color={theme.palette.warning.main}
					/>
				</Grid>
			</Grid>

			{/* Middle Section: Usage Analytics & Feature Breakdown */}
			<Grid container spacing={3} alignItems="stretch">
				{/* Left: Daily Usage Trend Chart */}
				<Grid size={{ xs: 12, lg: 8 }}>
					<Card
						sx={{
							borderRadius: '16px',
							border: `1px solid ${theme.palette.divider}`,
							background: theme.gradients?.card || theme.palette.background.paper,
							boxShadow: 'none',
							height: '100%',
							display: 'flex',
							flexDirection: 'column',
						}}
					>
						<CardContent sx={{ p: { xs: 2.5, sm: 3 }, flex: 1, display: 'flex', flexDirection: 'column' }}>
							<Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2.5 }}>
								<Box>
									<Typography variant="h6" sx={{ fontWeight: 800, color: 'text.primary', letterSpacing: '-0.01em' }}>
										Daily Operations Trend
									</Typography>
									<Typography variant="body2" color="text.secondary">
										Credit consumption activity across the last 30 calendar days
									</Typography>
								</Box>
								<Chip
									label="Daily View"
									size="small"
									sx={{
										fontWeight: 700,
										fontSize: '0.72rem',
										bgcolor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
									}}
								/>
							</Stack>

							{chartData.length > 0 ? (
								<Box sx={{ width: '100%', height: 280, mt: 'auto' }}>
									<ResponsiveContainer width="100%" height="100%">
										<AreaChart data={chartData} margin={{ top: 10, right: 15, left: -15, bottom: 0 }}>
											<defs>
												<linearGradient id="aiUsageGradient" x1="0" y1="0" x2="0" y2="1">
													<stop offset="5%" stopColor={brand} stopOpacity={isDark ? 0.45 : 0.25} />
													<stop offset="95%" stopColor={brand} stopOpacity={0} />
												</linearGradient>
											</defs>
											<CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)'} />
											<XAxis dataKey="date" tickLine={false} axisLine={false} style={{ fontSize: '0.72rem', fontWeight: 600, fill: theme.palette.text.secondary }} />
											<YAxis tickLine={false} axisLine={false} width={45} style={{ fontSize: '0.72rem', fontWeight: 600, fill: theme.palette.text.secondary }} />
											<Tooltip
												cursor={{ stroke: brand, strokeWidth: 1.5, strokeDasharray: '3 3' }}
												contentStyle={{
													background: theme.palette.background.paper,
													border: `1px solid ${theme.palette.divider}`,
													borderRadius: 10,
													fontSize: 12,
													fontWeight: 600,
													boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
												}}
												formatter={(value) => [`${Number(value).toLocaleString()} credits`, 'Consumed']}
											/>
											<Area type="monotone" dataKey="credits" stroke={brand} strokeWidth={2.5} fillOpacity={1} fill="url(#aiUsageGradient)" />
										</AreaChart>
									</ResponsiveContainer>
								</Box>
							) : (
								<Box
									sx={{
										flex: 1,
										minHeight: 220,
										display: 'flex',
										flexDirection: 'column',
										alignItems: 'center',
										justifyContent: 'center',
										p: 3,
										textAlign: 'center',
										borderRadius: '12px',
										bgcolor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)',
										border: `1px dashed ${theme.palette.divider}`,
									}}
								>
									<SparklesIcon sx={{ fontSize: 36, color: 'text.secondary', opacity: 0.5, mb: 1 }} />
									<Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary' }}>
										No AI Operations Recorded Yet
									</Typography>
									<Typography variant="body2" color="text.secondary" sx={{ maxWidth: 380, mt: 0.5 }}>
										Your agent tasks, chat completions, and automated workflows will automatically reflect in this daily trend chart.
									</Typography>
								</Box>
							)}
						</CardContent>
					</Card>
				</Grid>

				{/* Right: Breakdown by Feature */}
				<Grid size={{ xs: 12, lg: 4 }}>
					<Card
						sx={{
							borderRadius: '16px',
							border: `1px solid ${theme.palette.divider}`,
							background: theme.gradients?.card || theme.palette.background.paper,
							boxShadow: 'none',
							height: '100%',
							display: 'flex',
							flexDirection: 'column',
						}}
					>
						<CardContent sx={{ p: { xs: 2.5, sm: 3 }, flex: 1, display: 'flex', flexDirection: 'column' }}>
							<Typography variant="h6" sx={{ fontWeight: 800, color: 'text.primary', mb: 0.5 }}>
								Feature Breakdown
							</Typography>
							<Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
								Credits distributed by AI capability
							</Typography>

							{actionRows.length > 0 ? (
								<Stack spacing={2.5} sx={{ mt: 'auto', mb: 'auto' }}>
									{actionRows.map((row) => {
										const pct = ((row.credits / maxActionCredits) * 100);
										return (
											<Box key={row.action_type}>
												<Stack direction="row" justifyContent="space-between" alignItems="baseline" sx={{ mb: 0.75 }}>
													<Typography variant="body2" sx={{ fontWeight: 700, color: 'text.primary' }}>
														{prettifyActionType(row.action_type)}
													</Typography>
													<Typography variant="caption" sx={{ fontWeight: 700, color: brand }}>
														{row.credits.toLocaleString()} credits <span style={{ color: theme.palette.text.secondary, fontWeight: 500 }}>({row.calls} calls)</span>
													</Typography>
												</Stack>
												<LinearProgress
													variant="determinate"
													value={pct}
													sx={{
														height: 7,
														borderRadius: 4,
														bgcolor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)',
														'& .MuiLinearProgress-bar': {
															borderRadius: 4,
															background: theme.gradients?.brand || brand,
														},
													}}
												/>
											</Box>
										);
									})}
								</Stack>
							) : (
								<Box
									sx={{
										flex: 1,
										minHeight: 220,
										display: 'flex',
										flexDirection: 'column',
										alignItems: 'center',
										justifyContent: 'center',
										p: 3,
										textAlign: 'center',
										borderRadius: '12px',
										bgcolor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)',
										border: `1px dashed ${theme.palette.divider}`,
									}}
								>
									<InfoIcon sx={{ fontSize: 32, color: 'text.secondary', opacity: 0.5, mb: 1 }} />
									<Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
										Awaiting Operations
									</Typography>
									<Typography variant="body2" color="text.secondary" sx={{ maxWidth: 280, mt: 0.5, fontSize: '0.8rem' }}>
										Breakdowns populate automatically as team members execute AI calls.
									</Typography>
								</Box>
							)}
						</CardContent>
					</Card>
				</Grid>
			</Grid>

			{/* Bottom Section: Top-Up Credit Packages */}
			<Box id="topup-packages-section" sx={{ mt: 1 }}>
				<Box sx={{ mb: 3 }}>
					<Typography variant="h5" sx={{ fontWeight: 800, color: 'text.primary', letterSpacing: '-0.01em' }}>
						Instant Top-Up Packages
					</Typography>
					<Typography variant="body2" color="text.secondary">
						Need additional operations before your monthly cycle resets? Add instant credits to your wallet at any time.
					</Typography>
				</Box>

				<Grid container spacing={2.5} alignItems="stretch">
					{CREDIT_PACKAGES.map((pkg) => (
						<Grid size={{ xs: 12, sm: 6, lg: 3 }} key={pkg.credits} sx={{ display: 'flex' }}>
							<Card
								sx={{
									borderRadius: '18px',
									border: pkg.popular ? `2px solid ${brand}` : `1px solid ${theme.palette.divider}`,
									background: pkg.popular
										? isDark
											? 'linear-gradient(180deg, rgba(99, 102, 241, 0.12) 0%, rgba(30, 27, 75, 0.25) 100%)'
											: 'linear-gradient(180deg, rgba(238, 242, 255, 0.9) 0%, rgba(255, 255, 255, 1) 100%)'
										: theme.gradients?.card || theme.palette.background.paper,
									boxShadow: pkg.popular
										? isDark
											? `0 12px 32px -4px ${alpha(brand, 0.35)}`
											: `0 8px 24px -2px ${alpha(brand, 0.18)}`
										: 'none',
									position: 'relative',
									overflow: 'visible',
									width: '100%',
									display: 'flex',
									flexDirection: 'column',
									transition: 'all 0.25s ease',
									mt: pkg.popular ? { xs: 2, lg: 0 } : 0,
									'&:hover': {
										transform: 'translateY(-4px)',
										borderColor: brand,
										boxShadow: isDark
											? `0 16px 36px -4px ${alpha(brand, 0.45)}`
											: `0 12px 32px -2px ${alpha(brand, 0.2)}`,
									},
								}}
							>
								{/* Popular floating badge with overflow safe positioning */}
								{pkg.popular && (
									<Chip
										label="BEST VALUE"
										size="small"
										sx={{
											position: 'absolute',
											top: -13,
											left: '50%',
											transform: 'translateX(-50%)',
											bgcolor: theme.palette.primary.main,
											color: '#ffffff',
											fontWeight: 800,
											fontSize: '0.68rem',
											letterSpacing: '0.06em',
											px: 1.5,
											height: 24,
											boxShadow: `0 4px 12px ${alpha(brand, 0.4)}`,
											zIndex: 5,
										}}
									/>
								)}

								<CardContent sx={{ p: { xs: 2.5, sm: 3 }, flex: 1, display: 'flex', flexDirection: 'column' }}>
									<Box sx={{ textAlign: 'center', pb: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
										<Typography variant="h3" sx={{ fontWeight: 800, color: 'text.primary', lineHeight: 1.1 }}>
											{pkg.credits.toLocaleString()}
										</Typography>
										<Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 600, mb: 1.5 }}>
											AI Credits
										</Typography>
										<Typography variant="h4" sx={{ fontWeight: 800, color: brand, letterSpacing: '-0.02em' }}>
											{formatINR(pkg.price)}
										</Typography>
										<Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
											{pkg.effectiveRate}
										</Typography>
									</Box>

									{/* Feature perks list */}
									<Stack spacing={1.2} sx={{ my: 2.5, flex: 1 }}>
										{pkg.perks.map((perk, idx) => (
											<Stack key={idx} direction="row" spacing={1} alignItems="flex-start">
												<CheckIcon sx={{ fontSize: 16, color: 'success.main', mt: 0.2, flexShrink: 0 }} />
												<Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 500, lineHeight: 1.4 }}>
													{perk}
												</Typography>
											</Stack>
										))}
									</Stack>

									<Button
										fullWidth
										size="large"
										variant={pkg.popular ? 'contained' : 'outlined'}
										onClick={() => handleBuyClick(pkg)}
										sx={{
											textTransform: 'none',
											fontWeight: 700,
											borderRadius: '12px',
											py: 1.2,
											background: pkg.popular ? theme.gradients?.brand || brand : 'transparent',
											borderColor: pkg.popular ? 'transparent' : theme.palette.divider,
											boxShadow: 'none',
											'&:hover': {
												background: pkg.popular ? theme.gradients?.brandDiagonal || brand : alpha(brand, 0.05),
												borderColor: brand,
											},
										}}
									>
										Buy Package
									</Button>
								</CardContent>
							</Card>
						</Grid>
					))}
				</Grid>
			</Box>

			{/* Checkout & Payment Gateway Dialog */}
			<Dialog
				open={paymentDialogOpen}
				onClose={processingPayment ? undefined : () => setPaymentDialogOpen(false)}
				maxWidth="sm"
				fullWidth
				PaperProps={{
					sx: {
						borderRadius: '20px',
						overflow: 'hidden',
						bgcolor: theme.palette.background.paper,
						border: `1px solid ${theme.palette.divider}`,
						boxShadow: '0 24px 48px rgba(0, 0, 0, 0.25)',
					},
				}}
			>
				<DialogTitle
					sx={{
						background: theme.gradients?.brand || brand,
						color: '#ffffff',
						fontWeight: 800,
						py: 2.5,
						px: 3,
						display: 'flex',
						alignItems: 'center',
						gap: 1.5,
					}}
				>
					<CardIcon /> Instant Top-Up Checkout
				</DialogTitle>

				<form onSubmit={handlePaymentSubmit}>
					<DialogContent sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
						<Alert severity="info" sx={{ borderRadius: '12px' }}>
							You are purchasing <strong>{selectedPackage?.credits.toLocaleString()} AI credits</strong> for your account. Credits activate immediately upon confirmation.
						</Alert>

						{/* Order Summary box */}
						<Box
							sx={{
								p: 2.5,
								borderRadius: '14px',
								bgcolor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
								border: `1px solid ${theme.palette.divider}`,
							}}
						>
							<Typography variant="caption" sx={{ fontWeight: 800, mb: 1.5, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'text.secondary', display: 'block' }}>
								Order Invoice Breakdown
							</Typography>
							<Box display="flex" justifyContent="space-between" mb={1}>
								<Typography variant="body2" color="text.secondary">
									{selectedPackage?.credits.toLocaleString()} AI Credits ({selectedPackage?.effectiveRate})
								</Typography>
								<Typography variant="body2" sx={{ fontWeight: 700 }}>
									{formatINR(selectedPackage?.price || 0)}
								</Typography>
							</Box>
							<Box display="flex" justifyContent="space-between" mb={1}>
								<Typography variant="body2" color="text.secondary">GST (18%)</Typography>
								<Typography variant="body2" sx={{ fontWeight: 700 }}>
									{formatINR(Math.round((selectedPackage?.price || 0) * 0.18))}
								</Typography>
							</Box>
							<Divider sx={{ my: 1.5 }} />
							<Box display="flex" justifyContent="space-between" alignItems="center">
								<Typography variant="subtitle1" sx={{ fontWeight: 800 }}>Total Payable</Typography>
								<Typography variant="h6" color="primary" sx={{ fontWeight: 800 }}>
									{formatINR(Math.round((selectedPackage?.price || 0) * 1.18))}
								</Typography>
							</Box>
						</Box>

						{/* Payment details form */}
						<Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
							<Typography variant="caption" sx={{ fontWeight: 800, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'text.secondary' }}>
								Payment Card Details
							</Typography>
							<TextField
								required
								fullWidth
								label="Cardholder Name"
								value={cardName}
								onChange={(e) => setCardName(e.target.value)}
								disabled={processingPayment}
							/>
							<TextField
								required
								fullWidth
								label="Card Number"
								placeholder="4111 2222 3333 4444"
								value={cardNumber}
								onChange={(e) => setCardNumber(e.target.value.replace(/\D/g, '').replace(/(.{4})/g, '$1 ').trim().slice(0, 19))}
								disabled={processingPayment}
								InputProps={{
									startAdornment: (
										<InputAdornment position="start">
											<CardIcon sx={{ color: 'text.secondary', fontSize: 18 }} />
										</InputAdornment>
									),
								}}
							/>
							<Grid container spacing={2}>
								<Grid size={6}>
									<TextField
										required
										fullWidth
										label="Expiry Date"
										placeholder="MM/YY"
										value={cardExpiry}
										onChange={(e) => {
											let val = e.target.value.replace(/\D/g, '');
											if (val.length > 2) val = `${val.slice(0, 2)}/${val.slice(2, 4)}`;
											setCardExpiry(val.slice(0, 5));
										}}
										disabled={processingPayment}
									/>
								</Grid>
								<Grid size={6}>
									<TextField
										required
										fullWidth
										label="CVC / CVV"
										placeholder="123"
										type="password"
										value={cardCvc}
										onChange={(e) => setCardCvc(e.target.value.replace(/\D/g, '').slice(0, 4))}
										disabled={processingPayment}
									/>
								</Grid>
							</Grid>
						</Box>
					</DialogContent>
					<DialogActions sx={{ p: 3, pt: 0, gap: 1 }}>
						<Button
							onClick={() => setPaymentDialogOpen(false)}
							disabled={processingPayment}
							sx={{ textTransform: 'none', fontWeight: 600, borderRadius: '10px' }}
						>
							Cancel
						</Button>
						<Button
							type="submit"
							variant="contained"
							disabled={processingPayment}
							startIcon={processingPayment ? <CircularProgress size={16} sx={{ color: 'inherit' }} /> : undefined}
							sx={{
								textTransform: 'none',
								fontWeight: 700,
								borderRadius: '10px',
								px: 3,
								background: theme.gradients?.brand || brand,
								boxShadow: 'none',
							}}
						>
							{processingPayment ? 'Processing...' : `Pay ${formatINR(Math.round((selectedPackage?.price || 0) * 1.18))}`}
						</Button>
					</DialogActions>
				</form>
			</Dialog>
		</Box>
	);
};

export default AICreditsUsagePage;
