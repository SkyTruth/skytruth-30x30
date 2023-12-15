## Analysis cloud function

This cloud function is used to run a spatial analysis based on user custom area on the data that is stored in the database.

### Input call

```bash
curl '{url}' \
  -H 'content-type: application/json' \
  --data-raw '{"id":"d7c9978f92fff5a373f2dec55e17bbab","type":"Feature","properties":{},"geometry":{"coordinates":[[[-22.791446197507895,9.57642078480319],[-13.563358667514933,11.633521660754937],[0.7068797809280056,5.048301327696478],[-7.5698585191689745,-4.074667696937624],[-22.791446197507895,9.57642078480319]]],"type":"Polygon"}}' \
  --compressed

```

service: `https://30x30.skytruth.org/functions/analysis/`
locally: `http://0.0.0.0:3001`

### Output Response

```json
{locations_area:[{"code":<location_iso>, "protected_area": <area>, "area":<location_marine_area>}], "total_area":<total_area>, "total_protected_area":<total_area>}
```

### Development instructions

#### local development

In order to run the analysis locally you will need to:

1.- Set up a local postgres db, or connect to the staging db using the bastion host proxy.
2.- Create a virtual environment and install the requirements.
3.- Set the environment variables.
4.- Run the cloud function locally using the command `functions-framework --target=analysis --debug`

#### using docker & docker-compose

Prerequisites:
install docker and docker-compose

In order to run the analysis locally using docker you will need to:

1.- set the environment variables.
2.- run `docker-compose up --build`

Note: the first time you run this, you will need to run as well, once the db service is up, the `skytruth-db-init service` in order to populate the db with the data.
