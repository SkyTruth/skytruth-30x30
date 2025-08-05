export default {
  routes: [
    {
      method: 'POST',
      path: '/locations',
      handler: 'location.bulkUpsert'
    },
  ]
}