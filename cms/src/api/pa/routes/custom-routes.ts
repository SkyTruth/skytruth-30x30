export default {
  routes: [
    {
      method: 'POST',
      path: '/pas',
      handler: 'pa.bulkUpsert'
    },
    {
      method: 'PATCH',
      path: '/pas',
      handler: 'pa.bulkPatch'
    }
  ]
}