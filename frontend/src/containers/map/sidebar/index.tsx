import { useAtom } from 'jotai';
import { useTranslations } from 'next-intl';
import { LuChevronLeft } from 'react-icons/lu';

import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent } from '@/components/ui/collapsible';
import Icon from '@/components/ui/icon';
import { sidebarAtom, layersAtom } from '@/containers/map/store';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import { cn } from '@/lib/classnames';
import LayersIcon from '@/styles/icons/layers.svg';
import { FCWithMessages } from '@/types';

import { useSyncMapContentSettings } from '../sync-settings';

import LayersPanel from './layers-panel';
import MainPanel, { PANEL_TYPES } from './main-panel/panels';

type MapSidebarProps = {
  type: (typeof PANEL_TYPES)[keyof typeof PANEL_TYPES];
};

const MapSidebar: FCWithMessages<MapSidebarProps> = ({ type }) => {
  const t = useTranslations('containers.map-sidebar');

  const [{ showDetails }] = useSyncMapContentSettings();
  const [isSidebarOpen, setSidebarOpen] = useAtom(sidebarAtom);
  const [isLayersOpen, setLayersOpen] = useAtom(layersAtom);

  const testDate = useFeatureFlag('test_date');
  // const bad = useFeatureFlag('bad_feature_flag');
  console.log('MapSidebar rendered with testDate:', testDate);

  // Visibility (main panel/toggle)
  const showSidebar = true;
  const showSidebarToggle = !(isSidebarOpen && isLayersOpen) || showDetails;

  // Visibility (layers panel/toggle)
  const showLayersPanel = !showDetails;
  const showLayersToggle = showLayersPanel;

  return (
    <div className="relative z-20 flex h-full border-l border-black">
      {/* MAIN PANEL */}
      {showSidebar && (
        <div
          className={cn('relative z-10 border-b border-black bg-white', {
            'border-r': isSidebarOpen,
          })}
        >
          <Collapsible
            className="h-full overflow-hidden"
            open={isSidebarOpen}
            onOpenChange={setSidebarOpen}
          >
            <CollapsibleContent className="relative left-0 top-0 h-full flex-shrink-0 bg-white fill-mode-none data-[state=closed]:animate-collapsible-left data-[state=open]:animate-collapsible-right">
              <div className="h-full md:w-[460px]">
                <MainPanel type={type} />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      )}

      {/* SECONDARY PANEL (LAYERS) */}
      {showLayersPanel && (
        <div
          className={cn('relative z-20 border-b border-black bg-white', {
            'border-r': isLayersOpen,
          })}
        >
          <Collapsible
            className="h-full overflow-hidden"
            open={isLayersOpen}
            onOpenChange={setLayersOpen}
          >
            <CollapsibleContent className="relative left-0 top-0 h-full flex-shrink-0 bg-white fill-mode-none data-[state=closed]:animate-collapsible-left data-[state=open]:animate-collapsible-right">
              <div className="h-full md:w-[280px]">
                <LayersPanel />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      )}

      {/* BUTTONS */}
      <div className="relative z-30">
        {/* Layers Toggle */}
        {showLayersToggle && (
          <Button
            type="button"
            variant="white"
            className={cn('absolute top-0 -mt-px h-10 border-l-0 !py-3', {
              'hidden md:flex': true,
              'px-1': isLayersOpen,
              'border-l border-black px-3': !isLayersOpen,
              '-ml-px': (isSidebarOpen && !isLayersOpen) || (!isSidebarOpen && !isLayersOpen),
            })}
            onClick={() => setLayersOpen(!isLayersOpen)}
          >
            {isLayersOpen && (
              <>
                <LuChevronLeft className="-mx-0.5 h-5 w-5" aria-hidden />
                <span className="sr-only">{t('close-layers')}</span>
              </>
            )}
            {!isLayersOpen && (
              <>
                <Icon icon={LayersIcon} className="ml-0.5 h-4 w-4 pb-px" />
                <span className="whitespace-break-spaces pl-3 pr-1 font-mono text-xs font-normal normal-case">
                  {t('map-layers')}
                </span>
              </>
            )}
          </Button>
        )}

        {/* Sidebar Toggle */}
        {showSidebarToggle && (
          <Button
            type="button"
            variant="white"
            className={cn('absolute bottom-0 h-10 border-l-0 !py-3 px-1', {
              'hidden md:flex': true,
            })}
            onClick={() => setSidebarOpen(!isSidebarOpen)}
          >
            <LuChevronLeft
              className={cn('-ml-px h-5 w-5', { 'rotate-180': !isSidebarOpen })}
              aria-hidden
            />
            <span className="sr-only">{t('toggle-sidebar')}</span>
          </Button>
        )}
      </div>
    </div>
  );
};

MapSidebar.messages = ['containers.map-sidebar', ...MainPanel.messages, ...LayersPanel.messages];

export default MapSidebar;
