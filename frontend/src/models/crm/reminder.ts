export interface Reminder {
	id: number;
	public_id: string;
	title: string;
	description?: string;
	entity_type: string;
	entity_id: number;
	remind_at: string;
	status: 'pending' | 'completed' | 'dismissed' | 'sent';
	send_email?: boolean;
	user_id?: number;
	created_at: string;
	updated_at: string;
}
