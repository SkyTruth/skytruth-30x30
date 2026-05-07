export default ({ env }) => {
  // CMS_URL is e.g. 'https://.../cms/'. admin.url must be a full URL —
  // a bare path gets re-prefixed by server.url (urls.js:38), making
  // admin.path /cms/cms/admin and 404'ing every admin request. With a
  // same-origin full URL, Strapi subtracts the common prefix and derives
  // admin.path = '/admin', matching what reaches the container after the
  // LB rewrites /cms/* -> /*. The cookie path is the public-facing path
  // so the browser scopes the session cookie to /cms/admin/*.
  const cmsUrl = env('CMS_URL');
  const adminUrl = cmsUrl ? `${cmsUrl}admin` : '/admin';
  const cookiePath = adminUrl.startsWith('http') ? new URL(adminUrl).pathname : adminUrl;

  return {
    url: adminUrl,
    auth: {
      secret: env('ADMIN_JWT_SECRET'),
      cookie: { path: cookiePath },
    },
    apiToken: { salt: env('API_TOKEN_SALT') },
    transfer: { token: { salt: env('TRANSFER_TOKEN_SALT') } },
    watchIgnoreFiles: ['**/config/sync/**'],
  };
};
