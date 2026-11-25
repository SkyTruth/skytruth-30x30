import { useTranslations } from 'next-intl';

import { FCWithMessages } from '@/types';

import type { StatStatus } from '../helpers';

const StatStatusMessage: FCWithMessages<{ status: StatStatus }> = ({ status }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const tUploads = useTranslations('services.uploads');

  return (
    <p aria-live="polite" className="pt-3 font-mono text-xs empty:pt-0">
      {status === 'loading' && t('loading-data')}
      {status === 'error' && tUploads('general-stats-error')}
    </p>
  );
};

StatStatusMessage.messages = ['containers.map-sidebar-main-panel', 'services.uploads'];

export default StatStatusMessage;
