import { AlertTriangle } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { FCWithMessages } from '@/types';

type WarningProps = {
  toggleWarning: () => void;
};

const Warning: FCWithMessages<WarningProps> = ({ toggleWarning }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  return (
    <div className="inline-flex items-center border border-inherit px-2 text-xs">
      <AlertTriangle size="40" />
      <span className="pl-2">
        {t.rich('overlapping-eez-explainer', {
          a: (chunks) => (
            <a
              href="https://skytruth.atlassian.net/servicedesk/customer/portal/1/group/1/create/17"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              {chunks}
            </a>
          ),
          Button: (chunks) => (
            <Button
              type="button"
              variant="text-link"
              size="sm"
              onClick={toggleWarning}
              className="pl-1 py-0 pr-0 text-xs font-normal capitalize"
            >
              {chunks}
            </Button>
          ),
        })}
      </span>
    </div>
  );
};

Warning.messages = ['containers.map-sidebar-main-panel'];

export default Warning;
