import { useCallback, useEffect, useMemo, useRef } from 'react';

import { useRouter } from 'next/router';

import { useAtomValue } from 'jotai';
import { useTranslations } from 'next-intl';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PAGES } from '@/constants/pages';
import { useMapSearchParams } from '@/containers/map/content/map/sync-settings';
import { modellingAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useScrollPosition from '@/hooks/use-scroll-position';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

import LocationSelector from '../../location-selector';

import ModellingButtons from './modelling-buttons';
import ModellingIntro from './modelling-intro';
import ModellingWidget from './widget';

const SidebarModelling: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  const containerRef = useRef<HTMLDivElement | null>(null);
  const containerScroll = useScrollPosition(containerRef);

  const { push } = useRouter();
  const searchParams = useMapSearchParams();
  const { status: modellingStatus } = useAtomValue(modellingAtom);
  const [{ tab }, setSettings] = useSyncMapContentSettings();

  const showIntro = useMemo(() => modellingStatus === 'idle', [modellingStatus]);

  const handleLocationSelected = useCallback(
    (locationCode) => {
      push(`${PAGES.conservationBuilder}/${locationCode}?${searchParams.toString()}`);
    },
    [push, searchParams]
  );

  const handleTabChange = useCallback(
    (tab: string) => setSettings((prevSettings) => ({ ...prevSettings, tab })),
    [setSettings]
  );

  // Scroll to the top when the tab changes (whether that's initiated by clicking on the tab trigger
  // or programmatically via `setSettings` in a different component)
  useEffect(() => {
    containerRef.current?.scrollTo({ top: 0 });
  }, [tab]);

  // This page doesn't have a summary tab so we force the user to see the terrestrial tab if the
  // summary one was active
  useEffect(() => {
    if (tab === 'summary') {
      setSettings((prevSettings) => ({ ...prevSettings, tab: 'terrestrial' }));
    }
  }, [setSettings, tab]);

  return (
    <Tabs value={tab} onValueChange={handleTabChange} className="flex h-full w-full flex-col">
      <div className="flex flex-shrink-0 flex-col gap-y-2 border-b border-black bg-blue-600 px-4 pt-4 md:px-8 md:pt-6">
        <div
          className={cn({
            'flex gap-y-2 gap-x-5': true,
            'flex-col': containerScroll === 0,
            'flex-row': containerScroll > 0,
          })}
        >
          <h1
            className={cn({
              'text-ellipsis font-black transition-all': true,
              'text-5xl': containerScroll === 0,
              'overflow-hidden whitespace-nowrap text-xl': containerScroll > 0,
            })}
          >
            {showIntro ? t('conservation-scenarios') : t('custom-area')}
          </h1>
          <LocationSelector
            className="flex-shrink-0"
            theme="blue"
            size={containerScroll > 0 ? 'small' : 'default'}
            onChange={handleLocationSelected}
          />
        </div>
        {!showIntro && <p className="mt-2 font-black">{t('custom-area-description')}</p>}
        <TabsList className="relative top-px mt-5">
          <TabsTrigger value="terrestrial">{t('terrestrial')}</TabsTrigger>
          <TabsTrigger value="marine">{t('marine')}</TabsTrigger>
        </TabsList>
      </div>
      <div ref={containerRef} className="flex-grow overflow-y-auto">
        <TabsContent value="terrestrial">{showIntro && <ModellingIntro />}</TabsContent>
        <TabsContent value="marine">
          {showIntro && <ModellingIntro />}
          {!showIntro && <ModellingWidget />}
        </TabsContent>
      </div>
      <div className="shrink-0 border-t border-t-black bg-white px-4 py-5 md:px-8">
        <ModellingButtons />
      </div>
    </Tabs>
  );
};

SidebarModelling.messages = [
  'containers.map-sidebar-main-panel',
  ...LocationSelector.messages,
  ...ModellingButtons.messages,
  ...ModellingIntro.messages,
  ...ModellingWidget.messages,
];

export default SidebarModelling;
