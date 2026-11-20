import api from './api';
import type { DealProjectConversionPreview } from '../models/projects/project';

const crmService = {
	getDealProjectConversionPreview: async (dealPublicId: string): Promise<DealProjectConversionPreview> => {
		const res = await api.get(`/crm/deals/${dealPublicId}/convert-to-project/preview`);
		return res.data?.data || res.data;
	},
	convertDealToProject: async (dealPublicId: string, payload: any): Promise<any> => {
		const res = await api.post(`/crm/deals/${dealPublicId}/convert-to-project`, payload);
		return res.data?.data || res.data;
	},
};

export default crmService;
