import { useTranslations } from 'next-intl';

import { EXTERNAL_LINKS } from '@/constants/external-links';
import Layout from '@/layouts/error-page';
import { FCWithMessages } from '@/types';

export type ServiceUnavailableProps = {
  isMaintenance: boolean;
};

const ServiceUnavailable: FCWithMessages<ServiceUnavailableProps> = ({ isMaintenance }) => {
  const t = useTranslations('pages.503');

  const title = isMaintenance ? t('maintenance-page-title') : t('page-title');
  const description = t.rich(isMaintenance ? 'maintenance-page-description' : 'page-description', {
    link: (chunks) => (
      <a href={EXTERNAL_LINKS.supportEmail} className="underline">
        {chunks}
      </a>
    ),
  });

  return <Layout pageTitle={title} error={503} title={title} description={description} />;
};

ServiceUnavailable.messages = ['pages.503', ...Layout.messages];

export default ServiceUnavailable;
