import React from 'react';
import LegalPageLayout from '../../components/common/LegalPageLayout';
import privacyPolicyContent from '../../data/privacyPolicyContent';

const PrivacyPolicyPage: React.FC = () => (
	<LegalPageLayout
		pageTitle="Privacy Policy | WinVinaya MIS"
		metaDescription="How WinVinaya MIS collects, uses, stores, and protects personal data, designed & powered by WinVinaya InfoSystems."
		content={privacyPolicyContent}
	/>
);

export default PrivacyPolicyPage;
