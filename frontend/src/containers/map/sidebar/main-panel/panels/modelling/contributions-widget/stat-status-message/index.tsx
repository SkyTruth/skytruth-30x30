import { useTranslations } from 'next-intl';

import { FCWithMessages } from '@/types';

import type { StatStatus } from '../stat-status';

const StatStatusMessage: FCWithMessages<{ status: StatStatus }> = ({ status }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const tUploads = useTranslations('services.uploads');

  if (status === 'success') return null;

  return (
    <p className="pt-3 font-mono text-xs">
      {status === 'loading' ? t('loading-data') : tUploads('general-stats-error')}
    </p>
  );
};

StatStatusMessage.messages = ['containers.map-sidebar-main-panel', 'services.uploads'];

export default StatStatusMessage;
