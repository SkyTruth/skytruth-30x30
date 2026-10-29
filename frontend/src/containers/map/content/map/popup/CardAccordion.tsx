import { ReactNode, useEffect, useRef, useState } from 'react';

import { ChevronDown } from 'lucide-react';

import {
  Accordion,
  AccordionContent,
  AccordionHeader,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

export type CardAccordionItem = {
  id: string;
  title: ReactNode;
  content: ReactNode;
};

const CardAccordion = ({ items }: { items: CardAccordionItem[] }) => {
  const [openId, setOpenId] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // Anchoring on the trigger rather than the content keeps this independent of
  // the expand animation.
  useEffect(() => {
    const container = scrollRef.current;
    const item = itemRefs.current[openId];
    if (!container || !item) return;

    container.scrollTop += item.getBoundingClientRect().top - container.getBoundingClientRect().top;
  }, [openId]);

  return (
    <div ref={scrollRef} className="max-h-[30vh] overflow-y-auto overflow-x-hidden">
      <Accordion
        type="single"
        collapsible
        className="divide-y"
        value={openId}
        onValueChange={setOpenId}
      >
        {items.map(({ id, title, content }) => (
          <AccordionItem
            value={id}
            key={id}
            ref={(element) => {
              itemRefs.current[id] = element;
            }}
          >
            <AccordionHeader>
              <AccordionTrigger className="group grid w-full grid-cols-6 justify-items-start gap-4 py-2 text-left">
                <span className="col-span-5 col-start-1 font-semibold">{title}</span>
                <ChevronDown
                  aria-hidden
                  className="ease-&lsqb;cubic-bezier(0.87,_0,_0.13,_1)&rsqb; transition-transform duration-300 group-data-[state=open]:rotate-180"
                />
              </AccordionTrigger>
            </AccordionHeader>
            <AccordionContent className="pb-1 text-xs">{content}</AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
};

export default CardAccordion;
