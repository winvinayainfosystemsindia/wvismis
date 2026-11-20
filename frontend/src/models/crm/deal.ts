export interface Deal {
	id: number;
	public_id: string;
	title: string;
	value?: number;
	currency?: string;
	owner_id?: number;
	company_id?: number;
	status?: string;
}
