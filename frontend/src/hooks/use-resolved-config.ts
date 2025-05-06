import { useEffect, useState } from 'react';

import { parseConfig } from '@/lib/json-converter';

export default function useResolvedConfig<Config>(
  params: Parameters<typeof parseConfig<Config>>[0]
) {
  const [config, setConfig] = useState<Config | null>(null);

  useEffect(() => {
    if (!params) {
      setConfig(null);
      return;
    }
    const updateConfig = async () => {
      setConfig(await parseConfig(params));
    };

    updateConfig();
  }, [params, setConfig]);

  return config;
}
