import React, { ReactNode } from 'react';

import { useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

type NoDataProps = {
  error?: boolean;
  message?: string | ReactNode;
  className?: string;
};

const NoData: FCWithMessages<NoDataProps> = ({ error = false, message, className }) => {
  const t = useTranslations('components.widget');

  return (
    <div className={cn('flex flex-col gap-8 px-14 py-12 text-center md:px-10 md:py-14', className)}>
      <p className="text-xs">
        {error && !message && t('not-visible-due-to-error')}
        {error && !!message && message}
        {!error && !message && t('no-data-available')}
        {!error && !!message && message}
      </p>
    </div>
  );
};

NoData.messages = ['components.widget'];

export default NoData;
