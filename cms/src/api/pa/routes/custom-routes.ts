export default {
  routes: [
    {
      method: 'PUT',
      path: '/pas',
      handler: 'pa.bulkUpdate'
    },
    {
      method: 'POST',
      path: '/pas',
      handler: 'pa.bulkInsert'
    },
    {
      method: 'PATCH',
      path: '/pas',
      handler: 'pa.bulkPatch'
    }
  ]
}