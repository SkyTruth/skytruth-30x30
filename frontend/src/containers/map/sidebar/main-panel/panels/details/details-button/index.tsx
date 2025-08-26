import { useCallback } from 'react';

import { useTranslations } from 'next-intl';
import { LuArrowRight } from 'react-icons/lu';

import { Button } from '@/components/ui/button';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

type DetailsButtonProps = {
  className?: HTMLDivElement['className'];
  locationType: string;
};

const DetailsButton: FCWithMessages<DetailsButtonProps> = ({ className, locationType }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  const [{ tab, showDetails }, setSettings] = useSyncMapContentSettings();

  const handleButtonClick = useCallback(() => {
    setSettings((prevSettings) => ({ ...prevSettings, showDetails: !prevSettings.showDetails }));
  }, [setSettings]);

  return (
    <Button
      className={cn(
        {
          'flex h-10 px-5 md:px-8': true,
          'border border-black bg-orange text-black hover:bg-orange': showDetails,
        },
        className
      )}
      size="full"
      onClick={handleButtonClick}
    >
      <span className="font-mono text-xs font-semibold normal-case">
        {tab === 'summary' && locationType === 'worldwide' && t('show-global-insights-table')}
        {tab === 'summary' && locationType === 'region' && t('show-region-insights-table')}
        {tab === 'summary' && locationType === 'country' && t('show-country-insights-table')}
        {tab === 'terrestrial' && t('show-terrestrial-insights-table')}
        {tab === 'marine' && t('show-marine-insights-table')}
      </span>
      <LuArrowRight className="ml-2.5 h-5 w-5" aria-hidden />
    </Button>
  );
};

DetailsButton.messages = ['containers.map-sidebar-main-panel'];

export default DetailsButton;
