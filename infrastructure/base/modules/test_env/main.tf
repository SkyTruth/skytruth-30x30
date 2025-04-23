
locals {
  test_cloud_function_env = {
    TEST_ENV_VAR      = true
  }
}

module "test_cloud_function" {
  source                           = "../cloudfunction"
  region                           = var.gcp_region
  project                          = var.gcp_project_id
  vpc_connector_name               = module.network.vpc_access_connector_name
  function_name                    = "${var.project_name}-test"
  description                      = "Test Cloud Function"
  source_dir                       = "${path.root}/../../cloud_functions/test"
  runtime                          = "python312"
  entry_point                      = "main"
  runtime_environment_variables    = local.test_cloud_function_env
  timeout_seconds                  = var.test_function_timeout_seconds
  available_memory                 = var.test_function_available_memory
  available_cpu                    = var.test_function_available_cpu
  max_instance_count               = var.test_function_max_instance_count
  max_instance_request_concurrency = var.test_function_max_instance_request_concurrency
}
