import { Camera } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { FCWithMessages } from '@/types';

const BUTTON_CLASSES = 'group bg-white';
const ICON_CLASSES = 'h-4 w-4 text-black group-hover:text-white';

const Screenshot: FCWithMessages = () => {
  const t = useTranslations('components.map');

  return (
    <div className="absolute right-0 top-20 z-10 border border-r-0 border-t-0 border-black">
      <Button type="button" size="icon" className={BUTTON_CLASSES}>
        <Camera className={ICON_CLASSES} aria-hidden />
        <span className="sr-only">{t('screenshot')}</span>
      </Button>
    </div>
  );
};

Screenshot.messages = ['components.map'];

export default Screenshot;
