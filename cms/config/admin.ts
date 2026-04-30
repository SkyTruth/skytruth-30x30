export default ({ env }) => {
  // Behind the /cms-prefixing LB, Strapi v5 needs admin.url + cookie path
  // to include the prefix or auth redirects 404 and the session cookie's
  // Path scope misses /cms/admin. CMS_URL is set by Terraform in deployed
  // envs and unset locally.
  const cmsUrl = env('CMS_URL');
  const adminPath = cmsUrl ? `${new URL(cmsUrl).pathname}admin` : '/admin';

  return {
    url: adminPath,
    auth: {
      secret: env('ADMIN_JWT_SECRET'),
      cookie: { path: adminPath },
    },
    apiToken: { salt: env('API_TOKEN_SALT') },
    transfer: { token: { salt: env('TRANSFER_TOKEN_SALT') } },
    watchIgnoreFiles: ['**/config/sync/**'],
  };
};
