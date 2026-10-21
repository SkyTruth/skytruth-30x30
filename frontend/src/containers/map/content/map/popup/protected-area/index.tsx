import { useEffect, useRef, useState } from 'react';

import { ChevronDown } from 'lucide-react';
import { useTranslations } from 'next-intl';

import {
  Accordion,
  AccordionContent,
  AccordionHeader,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

import {
  useClickedProtectedAreas,
  useMergedProtectedAreas,
  useProtectedAreaRecords,
} from './hooks';
import PaCard from './PaCard';
import { clickedCardKey } from './parse-tile-click';

// `layerSlug` comes from the CMS config; the popup reads every protected-area layer instead.
const ProtectedAreaPopup: FCWithMessages<{ layerSlug: string }> = () => {
  const t = useTranslations('containers.map');

  const [openPa, setOpenPa] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const clicked = useClickedProtectedAreas();
  const { rows, isFetching } = useProtectedAreaRecords(clicked);
  const mergedPas = useMergedProtectedAreas(clicked, rows);

  // Anchoring on the trigger rather than the content keeps this independent of
  // the expand animation.
  useEffect(() => {
    const container = scrollRef.current;
    const item = itemRefs.current[openPa];
    if (!container || !item) return;

    container.scrollTop += item.getBoundingClientRect().top - container.getBoundingClientRect().top;
  }, [openPa]);

  if (!clicked.length) return null;

  // Known before the fetch, so the popup's size is settled on first render.
  const cardCount = new Set(clicked.map(clickedCardKey)).size;

  return (
    <div
      ref={scrollRef}
      className={cn(
        cardCount > 1 ? 'max-h-[30vh] overflow-y-auto overflow-x-hidden' : 'flex flex-col gap-2'
      )}
    >
      {isFetching && <div className="my-4 text-center font-mono text-xl">{t('loading')}</div>}
      {!isFetching && !mergedPas.length && (
        <div className="my-4 text-center font-mono">{t('no-data-available')}</div>
      )}
      {!isFetching && mergedPas.length === 1 && <PaCard pa={mergedPas[0]} showName />}
      {!isFetching && mergedPas.length > 1 && (
        <Accordion
          type="single"
          collapsible
          className="divide-y"
          value={openPa}
          onValueChange={setOpenPa}
        >
          {mergedPas.map((pa) => (
            <AccordionItem
              value={pa.id}
              key={pa.id}
              ref={(element) => {
                itemRefs.current[pa.id] = element;
              }}
            >
              <AccordionHeader>
                <AccordionTrigger className="group grid w-full grid-cols-6 justify-items-start gap-4 py-2 text-left">
                  <span className="col-span-5 col-start-1 font-semibold">{pa.name}</span>
                  <ChevronDown
                    aria-hidden
                    className="ease-&lsqb;cubic-bezier(0.87,_0,_0.13,_1)&rsqb; transition-transform duration-300 group-data-[state=open]:rotate-180"
                  />
                </AccordionTrigger>
              </AccordionHeader>
              <AccordionContent className="pb-1 text-xs">
                <PaCard pa={pa} />
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      )}
    </div>
  );
};

ProtectedAreaPopup.messages = [
  ...PaCard.messages,
  // Required by the `useLocationName` hook
  'locations',
];

export default ProtectedAreaPopup;
