export default [
  'strapi::logger',
  'strapi::errors',
  'strapi::security',
   {
    name: "strapi::cors",
    config: {
      origin: "*",
      headers: [
        "Content-Type",
        "Authorization",
        "Origin",
        "Accept",
        "Strapi-Response-Format",
      ],
    },
  },
  'strapi::poweredBy',
  'strapi::query',
  {
    name: 'strapi::body',
    config: {
      jsonLimit: '250mb',
    },
  },
  'strapi::session',
  'strapi::favicon',
  'strapi::public',
];
