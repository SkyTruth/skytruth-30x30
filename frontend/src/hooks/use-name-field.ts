import { useLocale } from 'next-intl';

import { useEffect, useState } from 'react';

export default function useNameField() {
  const locale = useLocale();
  const [nameField, setNameField] = useState('name');

  useEffect(() => {
      let name = 'name';
      switch(locale) {
        case 'en':
          name = 'name';
          break;
        case 'es':
          name = 'name_es';
          break;
        case 'fr':
          name = 'name_fr';
          break;
        case 'pt':
          name = 'name_pt';
          break;
      }
      setNameField(name);
    }, [locale]);

    return nameField;
}

