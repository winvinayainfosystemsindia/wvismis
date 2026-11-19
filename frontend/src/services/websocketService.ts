/**
 * Real-time WebSocket Service with Multi-Tenant Synchronization,
 * Automatic Reconnection, Heartbeat Ping/Pong, and Cache Invalidation.
 */

import authService from './authService';
import { store } from '../store/store';
import { setCreditBalance } from '../store/slices/aiSlice';
import { fetchCurrentUser } from '../store/slices/authSlice';
import { invalidateApiCache } from './api';

type WSEventHandler = (data: any) => void;

class WebSocketService {
	private ws: WebSocket | null = null;
	private reconnectTimer: any = null;
	private heartbeatTimer: any = null;
	private reconnectAttempts = 0;
	private readonly maxReconnectDelay = 15000;
	private handlers: Map<string, Set<WSEventHandler>> = new Map();
	private isIntentionallyClosed = false;

	/**
	 * Establish authenticated WebSocket connection
	 */
	public connect(): void {
		const token = authService.getAccessToken();
		if (!token) {
			return;
		}

		if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
			return;
		}

		this.isIntentionallyClosed = false;

		const apiUrl = import.meta.env.VITE_API_URL;
		const wsProtocol = apiUrl.startsWith('https') ? 'wss:' : 'ws:';
		const host = apiUrl.replace(/^https?:\/\//, '');
		const wsUrl = `${wsProtocol}//${host}/api/v1/ws/stream?token=${encodeURIComponent(token)}&channels=general,notifications,ai_agent`;

		try {
			this.ws = new WebSocket(wsUrl);

			this.ws.onopen = () => {
				this.reconnectAttempts = 0;
				this.startHeartbeat();
			};

			this.ws.onmessage = (event: MessageEvent) => {
				try {
					const payload = JSON.parse(event.data);
					this.handleMessage(payload);
				} catch {
					// Ignore non-json frames
				}
			};

			this.ws.onerror = () => {
				// Errors will trigger onclose where reconnect is handled
			};

			this.ws.onclose = () => {
				this.stopHeartbeat();
				this.ws = null;
				if (!this.isIntentionallyClosed) {
					this.scheduleReconnect();
				}
			};
		} catch {
			this.scheduleReconnect();
		}
	}

	/**
	 * Terminate WebSocket connection
	 */
	public disconnect(): void {
		this.isIntentionallyClosed = true;
		this.stopHeartbeat();
		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
		if (this.ws) {
			this.ws.close();
			this.ws = null;
		}
	}

	/**
	 * Subscribe to an event topic
	 */
	public on(event: string, handler: WSEventHandler): () => void {
		if (!this.handlers.has(event)) {
			this.handlers.set(event, new Set());
		}
		this.handlers.get(event)!.add(handler);
		return () => this.off(event, handler);
	}

	/**
	 * Unsubscribe from an event topic
	 */
	public off(event: string, handler: WSEventHandler): void {
		const set = this.handlers.get(event);
		if (set) {
			set.delete(handler);
			if (set.size === 0) {
				this.handlers.delete(event);
			}
		}
	}

	/**
	 * Send client command over WebSocket
	 */
	public send(action: string, payload: Record<string, any> = {}): boolean {
		if (this.ws && this.ws.readyState === WebSocket.OPEN) {
			this.ws.send(JSON.stringify({ action, ...payload }));
			return true;
		}
		return false;
	}

	private handleMessage(payload: { event?: string; channel?: string; data?: any }): void {
		const eventName = payload.event;
		if (!eventName) return;

		// ── Real-Time Redux & Cache Updates ──────────────────────────
		if (eventName === 'credits_updated') {
			if (payload.data) {
				store.dispatch(setCreditBalance(payload.data));
			}
			invalidateApiCache('/credits');
			invalidateApiCache('/usage');
		} else if (eventName === 'plan_updated' || eventName === 'org_updated') {
			invalidateApiCache('/plans');
			invalidateApiCache('/auth/me');
			store.dispatch(fetchCurrentUser());
		} else if (eventName === 'user_updated') {
			invalidateApiCache('/auth/me');
			store.dispatch(fetchCurrentUser());
		}

		// Dispatch to subscribed UI listeners
		const registered = this.handlers.get(eventName);
		if (registered) {
			registered.forEach((fn) => {
				try {
					fn(payload.data);
				} catch {
					// Guard listener callback
				}
			});
		}
	}

	private startHeartbeat(): void {
		this.stopHeartbeat();
		this.heartbeatTimer = setInterval(() => {
			if (this.ws && this.ws.readyState === WebSocket.OPEN) {
				this.ws.send(JSON.stringify({ action: 'ping' }));
			}
		}, 25000);
	}

	private stopHeartbeat(): void {
		if (this.heartbeatTimer) {
			clearInterval(this.heartbeatTimer);
			this.heartbeatTimer = null;
		}
	}

	private scheduleReconnect(): void {
		if (this.reconnectTimer) return;
		this.reconnectAttempts += 1;
		const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), this.maxReconnectDelay);
		this.reconnectTimer = setTimeout(() => {
			this.reconnectTimer = null;
			this.connect();
		}, delay);
	}
}

export const wsService = new WebSocketService();
export default wsService;
