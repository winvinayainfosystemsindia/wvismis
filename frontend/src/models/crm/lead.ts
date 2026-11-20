export type LeadPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface Lead {
	id: number;
	public_id: string;
	title: string;
	priority: LeadPriority;
	owner_id?: number;
	estimated_value?: number;
	currency?: string;
	description?: string;
	tags?: string[];
}
