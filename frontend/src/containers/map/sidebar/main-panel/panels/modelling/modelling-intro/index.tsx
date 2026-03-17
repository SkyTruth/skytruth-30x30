import { useCallback, useState } from 'react';

import { BarChart4 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { LuChevronDown, LuChevronUp } from 'react-icons/lu';

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import { FCWithMessages } from '@/types';

const TRIGGER_CLASSES = 'group flex w-full items-center justify-between text-left';
const ICON_CLASSES = 'w-5 h-5 hidden shrink-0';

const ModellingIntro: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const isCustomLayersActive = useFeatureFlag('is_custom_layers_active');

  const [drawOpen, setDrawOpen] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(true);

  const parseTextWithStyle = useCallback(
    (textKey, className: string) => {
      return t.rich(textKey, {
        b: (chunks) => <span className={className}>{chunks}</span>,
        i: () => <BarChart4 className="inline h-4 w-4 pb-px" />,
      });
    },
    [t]
  );

  return (
    <div className="flex flex-col gap-4 px-4 py-4 md:px-8">
      <span className="text-xl/[1.5rem] font-bold">
        {parseTextWithStyle('draw-upload-directions', 'text-blue-600')}
      </span>

      <Collapsible open={drawOpen} onOpenChange={setDrawOpen}>
        <CollapsibleTrigger className={TRIGGER_CLASSES}>
          {parseTextWithStyle('draw-area', 'text-blue-600 font-bold text-lg')}
          <LuChevronDown className={`group-data-[state=closed]:block ${ICON_CLASSES}`} />
          <LuChevronUp className={`group-data-[state=open]:block ${ICON_CLASSES}`} />
        </CollapsibleTrigger>
        <CollapsibleContent className="data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
          <ol className="mt-4 flex flex-col gap-y-[0.625rem]">
            <li className="flex items-start">
              <p className="mr-[1rem] font-mono text-[1rem]">01</p>
              <p>{parseTextWithStyle('draw-step-1-description', 'font-bold text-[1rem]')}</p>
            </li>

            <li className="flex items-start">
              <p className="mr-[1rem] font-mono text-[1.125rem]">02</p>
              <p>{t('draw-step-2-description')}</p>
            </li>

            <li className="flex items-start">
              <p className="mr-[1rem] font-mono text-[1.125rem]">03</p>
              <p>{t('draw-step-3-description')}</p>
            </li>

            {isCustomLayersActive && (
              <li className="flex items-start">
                <p className="mr-[1rem] font-mono text-[1rem]">04</p>
                <p>{parseTextWithStyle('draw-step-4-description', 'font-bold text-[1rem]')}</p>
              </li>
            )}
          </ol>
        </CollapsibleContent>
      </Collapsible>

      {isCustomLayersActive && (
        <Collapsible open={uploadOpen} onOpenChange={setUploadOpen}>
          <CollapsibleTrigger className={TRIGGER_CLASSES}>
            {parseTextWithStyle('upload-area', 'text-blue-600 font-bold text-lg')}
            <LuChevronDown className={`group-data-[state=closed]:block ${ICON_CLASSES}`} />
            <LuChevronUp className={`group-data-[state=open]:block ${ICON_CLASSES}`} />
          </CollapsibleTrigger>
          <CollapsibleContent className="data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
            <ol className="mt-4 flex flex-col gap-y-[0.625rem]">
              <li className="flex items-start gap-x-[1rem]">
                <p className="font-mono text-[1.125rem]">01</p>
                <p>{parseTextWithStyle('upload-step-1-description', 'font-bold')}</p>
              </li>

              <li className="flex items-start">
                <p className="mr-[1rem] font-mono text-[1.125rem]">02</p>
                <p>{t('upload-step-2-description')}</p>
              </li>

              <li className="flex items-start">
                <p className="mr-[1rem] font-mono text-[1.125rem]">03</p>
                <p>{t('upload-step-3-description')}</p>
              </li>

              <li className="flex items-start">
                <p className="mr-[1rem] font-mono text-[1.125rem]">04</p>
                <p>{parseTextWithStyle('upload-step-4-description', 'font-bold text-[1rem]')}</p>
              </li>
            </ol>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
};

ModellingIntro.messages = ['containers.map-sidebar-main-panel'];

export default ModellingIntro;
