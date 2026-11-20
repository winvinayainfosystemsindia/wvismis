import React from 'react';
import LegalPageLayout from '../../components/common/LegalPageLayout';
import termsAndConditionsContent from '../../data/termsAndConditionsContent';

const TermsPage: React.FC = () => (
	<LegalPageLayout
		pageTitle="Terms and Conditions | WinVinaya MIS"
		metaDescription="The terms governing access to and use of WinVinaya MIS, designed & powered by WinVinaya InfoSystems."
		content={termsAndConditionsContent}
	/>
);

export default TermsPage;
