import { useState } from 'react';

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@radix-ui/react-collapsible';
import { useTranslations } from 'next-intl';
import { LuChevronDown } from 'react-icons/lu';

import Icon from '@/components/ui/icon';
import LegendIcon from '@/styles/icons/legend.svg';
import { FCWithMessages } from '@/types';

import LayersLegend from './legend';

const LayersToolbox: FCWithMessages = () => {
  const t = useTranslations('containers.map');

  const [open, setOpen] = useState(true);

  return (
    <div className="absolute bottom-0 right-0 z-20 bg-red">
      <div className="relative">
        <Collapsible className="relative bg-red" open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger className="absolute top-0 right-0 -translate-y-full border border-b-0 border-black bg-white">
            {open && <LuChevronDown className="mx-2 my-px h-5 w-5" aria-hidden />}
            {!open && (
              <span className="flex items-center gap-2 py-2.5 pl-3 pr-4 font-mono text-xs">
                <Icon icon={LegendIcon} className="ml-0.5 h-5 w-5" />
                <span className="pt-px">{t('legend')}</span>
              </span>
            )}
          </CollapsibleTrigger>
          <CollapsibleContent className="border-l border-t border-black bg-white fill-mode-none data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
            <div className="relative h-full max-h-[calc(100vh-200px)] w-[300px] overflow-y-auto border ">
              <LayersLegend />
            </div>
          </CollapsibleContent>
        </Collapsible>
        <div className="absolute bottom-0 left-0 h-6 w-full bg-gradient-to-b from-transparent to-white" />
      </div>
    </div>
  );
};

LayersToolbox.messages = ['containers.map', ...LayersLegend.messages];

export default LayersToolbox;
