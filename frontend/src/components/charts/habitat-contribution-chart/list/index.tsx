import { PropsWithChildren } from 'react';

import { useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

/** Habitat rows sharing name, "Added" and "Total" columns */
const HabitatContributionList: FCWithMessages<PropsWithChildren<{ className?: string }>> = ({
  className,
  children,
}) => {
  const t = useTranslations('components.chart-contribution');

  return (
    <div className={cn('grid grid-cols-[1fr_auto_auto] gap-x-2', className)}>
      <span
        aria-hidden
        className="col-start-2 justify-self-center font-mono text-xs font-bold text-previous-value"
      >
        {t('added')}
      </span>
      <span
        aria-hidden
        className="justify-self-center font-mono text-xs font-bold text-previous-value"
      >
        {t('total')}
      </span>
      {children}
    </div>
  );
};

HabitatContributionList.messages = ['components.chart-contribution'];

export default HabitatContributionList;
