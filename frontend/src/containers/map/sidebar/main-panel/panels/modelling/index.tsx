import { useCallback, useEffect, useMemo, useRef } from 'react';

import { useAtomValue } from 'jotai';
import { useTranslations } from 'next-intl';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  customLayersAtom,
  modellingAtom,
  modellingCustomLayerIdAtom,
} from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import useMapDefaultLayers from '@/hooks/use-map-default-layers';
import useScrollPosition from '@/hooks/use-scroll-position';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

import LocationSelector from '../../location-selector';

import ModellingButtons from './modelling-buttons';
import ModellingIntro from './modelling-intro';
import ModellingWidget from './widget';

const SidebarModelling: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  const contentRef = useRef<HTMLDivElement | null>(null);
  const contentScroll = useScrollPosition(contentRef);

  const { status: modellingStatus } = useAtomValue(modellingAtom);
  const modellingCustomLayerId = useAtomValue(modellingCustomLayerIdAtom);
  const customLayers = useAtomValue(customLayersAtom);
  const [{ tab }, setSettings] = useSyncMapContentSettings();

  const isCustomLayersActive = useFeatureFlag('is_custom_layers_active'); // TODO: TECH-3372 Teardown

  const showIntro = useMemo(() => modellingStatus === 'idle', [modellingStatus]);

  // Keep default map layers in sync with selected tab/environment.
  useMapDefaultLayers();

  const handleTabChange = useCallback(
    (tab: string) => setSettings((prevSettings) => ({ ...prevSettings, tab })),
    [setSettings]
  );

  // Scroll to the top when the tab changes (whether that's initiated by clicking on the tab trigger
  // or programmatically via `setSettings` in a different component)
  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0 });
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
        <div>
          <h1
            className={cn({
              'font-black transition-all': true,
              truncate: !showIntro,
              'min-h-[3rem] text-5xl': !isCustomLayersActive || contentScroll === 0,
              'min-h-[1.75rem] text-xl': isCustomLayersActive && contentScroll > 0,
            })}
          >
            {showIntro
              ? t('conservation-scenarios')
              : (modellingCustomLayerId && customLayers[modellingCustomLayerId]?.name) ||
                t('custom-area')}
          </h1>
        </div>
        {!showIntro && <p className="mt-2 font-black">{t('custom-area-description')}</p>}
        <TabsList className="relative top-px mt-5">
          <TabsTrigger value="terrestrial">{t('terrestrial')}</TabsTrigger>
          <TabsTrigger value="marine">{t('marine')}</TabsTrigger>
        </TabsList>
      </div>
      <div ref={contentRef} className="flex-grow overflow-y-auto">
        <TabsContent value="terrestrial">
          {showIntro && <ModellingIntro />}
          {!showIntro && <ModellingWidget />}
        </TabsContent>
        <TabsContent value="marine">
          {showIntro && <ModellingIntro />}
          {!showIntro && <ModellingWidget />}
        </TabsContent>
      </div>
      <div className="shrink-0 border-t border-t-black bg-white py-5">
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
