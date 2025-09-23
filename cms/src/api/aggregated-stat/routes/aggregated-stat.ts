export default {
  routes: [
    {
     method: 'GET',
     path: '/aggregated-stats',
     handler: 'aggregated-stat.getStats',
     config: {
       policies: [],
       middlewares: [],
     },
    },
  ],
};
