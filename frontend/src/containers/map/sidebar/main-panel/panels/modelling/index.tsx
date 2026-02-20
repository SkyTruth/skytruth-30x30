import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useAtomValue } from 'jotai';
import { useTranslations } from 'next-intl';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { modellingAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useMapDefaultLayers from '@/hooks/use-map-default-layers';
import { FCWithMessages } from '@/types';

import LocationSelector from '../../location-selector';

import ModellingButtons from './modelling-buttons';
import ModellingIntro from './modelling-intro';
import ModellingWidget from './widget';

const SidebarModelling: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  const [headerSize, setHeaderSize] = useState<string | null>(null);

  const contentRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const { status: modellingStatus } = useAtomValue(modellingAtom);
  const [{ tab }, setSettings] = useSyncMapContentSettings();

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

  // Dynamically shrink the panel header based on available height
  useEffect(() => {
    const updateHeight = () => {
      if (containerRef.current) {
        let textSize = 'text-xl';
        const {
          current: { clientHeight },
        } = containerRef;

        if (clientHeight <= 700 && clientHeight > 630) {
          textSize = 'text-3xl';
        }
        if (clientHeight > 700) {
          textSize = 'text-5xl';
        }
        setHeaderSize(textSize);
      }
    };

    updateHeight();
    window.addEventListener('resize', updateHeight);

    return () => window.removeEventListener('resize', updateHeight);
  }, []);

  return (
    <Tabs
      value={tab}
      onValueChange={handleTabChange}
      className="flex h-full w-full flex-col"
      ref={containerRef}
    >
      <div className="flex flex-shrink-0 flex-col gap-y-2 border-b border-black bg-blue-600 px-4 pt-4 md:px-8 md:pt-6">
        <div>
          <h1 className={`text-ellipsis font-black transition-all ${headerSize}`}>
            {showIntro ? t('conservation-scenarios') : t('custom-area')}
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
